from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, hsts_max_age: int = 63072000):
        super().__init__(app)
        self.hsts_max_age = hsts_max_age

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        scheme = forwarded_proto.split(",")[0].strip() if forwarded_proto else request.url.scheme
        if scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={self.hsts_max_age}; includeSubDomains; preload",
            )

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")

        return response
