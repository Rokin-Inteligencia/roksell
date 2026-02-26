from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import or_

from app import models
from app.db import SessionLocal

logger = logging.getLogger(__name__)

CHECK_INTERVAL_HOURS = int(os.getenv("WHATSAPP_MEDIA_CLEANUP_INTERVAL_HOURS", "48"))
RETENTION_DAYS = int(os.getenv("WHATSAPP_MEDIA_RETENTION_DAYS", "30"))
MAX_PER_RUN = int(os.getenv("WHATSAPP_MEDIA_CLEANUP_LIMIT", "500"))


async def _is_media_missing(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.head(url)
            if resp.status_code in {404, 410}:
                return True
            if resp.status_code == 405:
                resp = await client.get(url)
                if resp.status_code in {404, 410}:
                    return True
            return False
    except Exception:
        logger.exception("Failed to check media url")
        return False


async def cleanup_invalid_whatsapp_media_once() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    db = SessionLocal()
    try:
        rows = (
            db.query(models.WhatsAppInboundMessage)
            .filter(models.WhatsAppInboundMessage.media_url.isnot(None))
            .filter(models.WhatsAppInboundMessage.media_url != "")
            .filter(models.WhatsAppInboundMessage.created_at <= cutoff)
            .order_by(models.WhatsAppInboundMessage.created_at.asc())
            .limit(MAX_PER_RUN)
            .all()
        )
        if not rows:
            return
        removed = 0
        for row in rows:
            url = (row.media_url or "").strip()
            if not url:
                continue
            missing = await _is_media_missing(url)
            if missing:
                row.media_url = None
                row.media_mime = None
                removed += 1
        if removed:
            db.commit()
            logger.info("WhatsApp media cleanup removed=%s", removed)
    finally:
        db.close()


async def run_whatsapp_media_cleanup_loop() -> None:
    enabled = os.getenv("WHATSAPP_MEDIA_CLEANUP_ENABLED", "true").strip().lower() not in {"0", "false", "no"}
    if not enabled:
        logger.info("WhatsApp media cleanup disabled")
        return
    interval = max(1, CHECK_INTERVAL_HOURS) * 60 * 60
    while True:
        try:
            await cleanup_invalid_whatsapp_media_once()
        except Exception:
            logger.exception("WhatsApp media cleanup failed")
        await asyncio.sleep(interval)
