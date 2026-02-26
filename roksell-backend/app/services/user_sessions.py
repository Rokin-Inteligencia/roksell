import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import models


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_max_active_sessions(value: int | None, default: int = 3) -> int:
    parsed = default if value is None else int(value)
    if parsed < 1:
        return 1
    if parsed > 20:
        return 20
    return parsed


def _active_sessions_query(
    db: Session,
    *,
    user_id: str,
    tenant_id: str,
):
    now = utc_now()
    return (
        db.query(models.UserSession)
        .filter(
            models.UserSession.user_id == user_id,
            models.UserSession.tenant_id == tenant_id,
            models.UserSession.revoked_at.is_(None),
            models.UserSession.expires_at > now,
        )
    )


def trim_user_sessions_to_limit(
    db: Session,
    *,
    user: models.User,
    tenant_id: str,
) -> None:
    limit = normalize_max_active_sessions(user.max_active_sessions)
    active_sessions = (
        _active_sessions_query(db, user_id=user.id, tenant_id=tenant_id)
        .order_by(models.UserSession.created_at.desc(), models.UserSession.id.desc())
        .all()
    )
    if len(active_sessions) <= limit:
        return
    revoked_at = utc_now()
    for session in active_sessions[limit:]:
        session.revoked_at = revoked_at
        session.revoked_reason = "limit_exceeded"


def create_user_session(
    db: Session,
    *,
    user: models.User,
    tenant_id: str,
    ttl_minutes: int,
) -> tuple[str, datetime]:
    now = utc_now()
    expires_at = now + timedelta(minutes=max(5, int(ttl_minutes)))
    session_id = str(uuid.uuid4())
    db.add(
        models.UserSession(
            id=session_id,
            user_id=user.id,
            tenant_id=tenant_id,
            created_at=now,
            expires_at=expires_at,
        )
    )
    user.last_login_at = now
    trim_user_sessions_to_limit(db, user=user, tenant_id=tenant_id)
    return session_id, expires_at


def revoke_user_session(
    db: Session,
    *,
    user_id: str,
    tenant_id: str,
    session_id: str,
    reason: str,
) -> None:
    session = (
        db.query(models.UserSession)
        .filter(
            models.UserSession.id == session_id,
            models.UserSession.user_id == user_id,
            models.UserSession.tenant_id == tenant_id,
            models.UserSession.revoked_at.is_(None),
        )
        .first()
    )
    if not session:
        return
    session.revoked_at = utc_now()
    session.revoked_reason = reason


def is_user_session_active(
    db: Session,
    *,
    user_id: str,
    tenant_id: str,
    session_id: str,
) -> bool:
    return (
        _active_sessions_query(db, user_id=user_id, tenant_id=tenant_id)
        .filter(models.UserSession.id == session_id)
        .first()
        is not None
    )
