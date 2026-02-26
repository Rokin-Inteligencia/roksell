from __future__ import annotations

import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger("app.request")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - start) * 1000)
            payload = self._build_payload(request, request_id, duration_ms, status=500)
            logger.exception(json.dumps(payload, ensure_ascii=True))
            raise

        duration_ms = int((time.perf_counter() - start) * 1000)
        payload = self._build_payload(request, request_id, duration_ms, status=response.status_code)
        if response.status_code >= 500:
            logger.error(json.dumps(payload, ensure_ascii=True))
        elif response.status_code >= 400:
            logger.warning(json.dumps(payload, ensure_ascii=True))
        else:
            logger.info(json.dumps(payload, ensure_ascii=True))

        response.headers["X-Request-Id"] = request_id
        return response

    @staticmethod
    def _build_payload(request: Request, request_id: str, duration_ms: int, status: int) -> dict:
        tenant = request.headers.get("x-tenant-id") or request.headers.get("x-tenant")
        forwarded = request.headers.get("x-forwarded-for")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
        return {
            "event": "http_request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": status,
            "duration_ms": duration_ms,
            "tenant": tenant,
            "client_ip": client_ip,
        }
