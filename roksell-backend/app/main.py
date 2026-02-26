import os
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.media import media_root, media_url, ensure_dir
from app.storage import is_local_storage
from app.observability import RequestLoggingMiddleware
from app.security_headers import SecurityHeadersMiddleware
from app.rate_limit import RateLimitMiddleware, RateLimitRule
from app.services.whatsapp_media_cleanup import run_whatsapp_media_cleanup_loop
from app.routers import (
    catalog,
    admin,
    orders,
    shipping,
    checkout,
    auth,
    users_admin,
    groups_admin,
    billing,
    billing_webhook,
    catalog_admin,
    config_admin,
    insights,
    customers_admin,
    campaigns_admin,
    stores,
    stores_admin,
    inventory_admin,
    admin_central,
    shipping_admin,
    whatsapp_admin,
    whatsapp_webhook,
)

app = FastAPI(title="Rokin API")

if is_local_storage():
    media_root_path = media_root()
    ensure_dir(media_root_path)
    app.mount(media_url(), StaticFiles(directory=str(media_root_path)), name="media")

ALLOWED_ORIGINS = [
    # Dev - Next/Vite
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.56.1:3000",
    # Prod
    "https://www.rokin.com.br",
    "https://rokin.com.br",
]

def _parse_env_list(name: str) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]

cors_origins = _parse_env_list("CORS_ALLOWED_ORIGINS") or ALLOWED_ORIGINS
trusted_hosts = _parse_env_list("TRUSTED_HOSTS")

if trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"], allow_headers=["*"], allow_credentials=True,
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    RateLimitMiddleware,
    rules=[
        RateLimitRule(path="/auth/login", max_requests=10, window_seconds=60, methods={"POST"}),
        RateLimitRule(path="/auth/signup", max_requests=5, window_seconds=60, methods={"POST"}),
        RateLimitRule(path="/checkout", max_requests=30, window_seconds=60, methods={"POST"}),
        RateLimitRule(path="/shipping/quote", max_requests=30, window_seconds=60, methods={"POST"}),
    ],
)

@app.on_event("startup")
async def start_background_tasks():
    asyncio.create_task(run_whatsapp_media_cleanup_loop())

@app.get("/health")
def health(): return {"ok": True}

app.include_router(catalog.router)
app.include_router(checkout.router)
app.include_router(orders.router)
app.include_router(admin.router)
app.include_router(shipping.router)
app.include_router(auth.router)
app.include_router(users_admin.router)
app.include_router(groups_admin.router)
app.include_router(billing.router)
app.include_router(billing_webhook.router)
app.include_router(catalog_admin.router)
app.include_router(config_admin.router)
app.include_router(insights.router)
app.include_router(customers_admin.router)
app.include_router(campaigns_admin.router)
app.include_router(stores.router)
app.include_router(stores_admin.router)
app.include_router(inventory_admin.router)
app.include_router(admin_central.router)
app.include_router(shipping_admin.router)
app.include_router(whatsapp_admin.router)
app.include_router(whatsapp_webhook.router)
