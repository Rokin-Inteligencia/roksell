from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Iterable
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

try:
    import redis.asyncio as redis  # type: ignore
except Exception:  # pragma: no cover - fallback when dependency is missing
    redis = None

logger = logging.getLogger("app.rate_limit")


@dataclass(frozen=True)
class RateLimitRule:
    path: str
    max_requests: int
    window_seconds: int
    methods: set[str] | None = None


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, rules: Iterable[RateLimitRule]) -> None:
        super().__init__(app)
        self._rules = list(rules)
        self._hits: dict[str, Deque[float]] = {}
        self._lock = asyncio.Lock()
        self._redis = None
        self._redis_error_logged = False
        self._redis_url = os.getenv("RATE_LIMIT_REDIS_URL") or os.getenv("REDIS_URL")
        self._redis_script = (
            "local current = redis.call('INCR', KEYS[1]) "
            "if current == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end "
            "local ttl = redis.call('TTL', KEYS[1]) "
            "return {current, ttl}"
        )
        if self._redis_url and redis is not None:
            self._redis = redis.from_url(self._redis_url, encoding="utf-8", decode_responses=True)
        elif self._redis_url and redis is None:
            logger.warning("Redis URL configured but redis package is missing; falling back to memory")

    async def dispatch(self, request: Request, call_next) -> Response:
        rule = self._match_rule(request)
        if rule is None:
            return await call_next(request)

        client_id = self._client_id(request)
        key = f"{client_id}:{rule.path}:{request.method}"

        allowed, retry_after = await self._check_limit(key, rule)
        if not allowed:
            return JSONResponse(
                {"detail": "Too many requests"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)

    async def _check_limit(self, key: str, rule: RateLimitRule) -> tuple[bool, int]:
        if self._redis is None:
            return await self._check_memory(key, rule)

        try:
            now = int(time.time())
            window_start = now - (now % rule.window_seconds)
            redis_key = f"rl:{key}:{window_start}"
            result = await self._redis.eval(self._redis_script, 1, redis_key, rule.window_seconds)
            current = int(result[0])
            ttl = int(result[1]) if result[1] is not None else rule.window_seconds
            if current > rule.max_requests:
                retry_after = max(1, ttl)
                return False, retry_after
            return True, 0
        except Exception as exc:
            if not self._redis_error_logged:
                logger.warning("Redis rate limiting failed; falling back to memory: %s", exc)
                self._redis_error_logged = True
            return await self._check_memory(key, rule)

    async def _check_memory(self, key: str, rule: RateLimitRule) -> tuple[bool, int]:
        now = time.monotonic()
        async with self._lock:
            bucket = self._hits.setdefault(key, deque())
            window_start = now - rule.window_seconds
            while bucket and bucket[0] <= window_start:
                bucket.popleft()
            if len(bucket) >= rule.max_requests:
                retry_after = max(1, int(rule.window_seconds - (now - bucket[0])))
                return False, retry_after
            bucket.append(now)
        return True, 0

    def _match_rule(self, request: Request) -> RateLimitRule | None:
        path = request.url.path
        method = request.method.upper()
        for rule in self._rules:
            if not path.startswith(rule.path):
                continue
            if rule.methods and method not in rule.methods:
                continue
            return rule
        return None

    @staticmethod
    def _client_id(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "unknown"
