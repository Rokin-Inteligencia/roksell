from datetime import datetime, timedelta
import hashlib
import hmac
from typing import Any, Dict

from jose import jwt
from passlib.context import CryptContext

from app.db import settings
from app.phone import phone_candidates

# Log da biblioteca bcrypt carregada (debug) e correção para __about__ ausente
import logging
try:
    import bcrypt  # noqa: E401
    if not hasattr(bcrypt, "__about__"):
        class _About:
            __version__ = getattr(bcrypt, "__version__", "unknown")
        bcrypt.__about__ = _About()
    logging.info(
        "[bcrypt] module=%s has_about=%s version=%s",
        getattr(bcrypt, "__file__", "?"),
        hasattr(bcrypt, "__about__"),
        getattr(getattr(bcrypt, "__about__", {}), "__version__", getattr(bcrypt, "__version__", None)),
    )
except Exception as exc:
    logging.exception("[bcrypt] failed to inspect bcrypt module: %s", exc)

# Usamos bcrypt_sha256 para evitar limite de 72 bytes e aceitar hashes antigos bcrypt.
pwd_context = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any], expires_minutes: int | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, settings.auth_secret, algorithm=settings.auth_algorithm)
    return token


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def create_order_tracking_token(order_id: str, phone: str) -> str:
    secret = (settings.order_tracking_secret or settings.auth_secret).encode()
    message = f"{order_id}:{_normalize_phone(phone)}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_order_tracking_token(token: str, order_id: str, phone: str) -> bool:
    candidates = phone_candidates(phone)
    if not candidates:
        candidates = [_normalize_phone(phone)]
    for candidate in candidates:
        message = f"{order_id}:{candidate}".encode()
        expected = hmac.new((settings.order_tracking_secret or settings.auth_secret).encode(), message, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, token):
            return True
    return False
