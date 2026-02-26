from typing import Callable

from fastapi import Cookie, Depends, Header, HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.db import get_db, settings
from app.domain.tenancy.access import (
    normalize_tenant_modules,
    permission_allows_action,
    user_allowed_modules,
    user_group_permissions,
)
from app.services.user_sessions import is_user_session_active
from app.tenancy import TenantContext, get_tenant_context


class TokenData(BaseModel):
    sub: str
    tenant_id: str
    role: str
    sid: str


def _decode_token(token: str) -> TokenData:
    payload = None
    last_error: Exception | None = None
    for secret in settings.AUTH_SECRETS_LIST:
        try:
            payload = jwt.decode(token, secret, algorithms=[settings.auth_algorithm])
            break
        except JWTError as exc:
            last_error = exc
            continue
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from last_error

    sub = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    role = payload.get("role")
    sid = payload.get("sid")
    if not sub or not tenant_id or not role or not sid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return TokenData(sub=sub, tenant_id=tenant_id, role=role, sid=sid)


def get_current_user(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    authorization: str | None = Header(default=None, alias="Authorization"),
    token_cookie: str | None = Cookie(default=None, alias="admin_token"),
) -> models.User:
    token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif token_cookie:
        token = token_cookie

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")

    token_data = _decode_token(token)
    if token_data.tenant_id != tenant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")

    user = (
        db.query(models.User)
        .filter(
            models.User.id == token_data.sub,
            models.User.tenant_id == tenant.id,
            models.User.is_active.is_(True),
        )
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not is_user_session_active(
        db,
        user_id=user.id,
        tenant_id=tenant.id,
        session_id=token_data.sid,
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or revoked")
    return user


def get_current_user_optional(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    authorization: str | None = Header(default=None, alias="Authorization"),
    token_cookie: str | None = Cookie(default=None, alias="admin_token"),
) -> models.User | None:
    token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif token_cookie:
        token = token_cookie

    if not token:
        return None

    token_data = _decode_token(token)
    if token_data.tenant_id != tenant.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")

    user = (
        db.query(models.User)
        .filter(
            models.User.id == token_data.sub,
            models.User.tenant_id == tenant.id,
            models.User.is_active.is_(True),
        )
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not is_user_session_active(
        db,
        user_id=user.id,
        tenant_id=tenant.id,
        session_id=token_data.sid,
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or revoked")
    return user


def require_roles(*roles: models.UserRole) -> Callable[[models.User], models.User]:
    def dependency(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
        return user

    return dependency


def require_module(module_key: str) -> Callable[[TenantContext], TenantContext]:
    def dependency(
        tenant: TenantContext = Depends(get_tenant_context),
        user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> TenantContext:
        allowed_modules = user_allowed_modules(db=db, user=user, tenant_modules=tenant.modules)
        if module_key not in allowed_modules:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Module disabled")
        return tenant

    return dependency


def require_module_action(module_key: str, action: str = "view") -> Callable[[TenantContext], TenantContext]:
    action_key = action.strip().lower()
    if action_key not in {"view", "edit"}:
        raise ValueError("action must be 'view' or 'edit'")

    def dependency(
        tenant: TenantContext = Depends(get_tenant_context),
        user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> TenantContext:
        module = (module_key or "").strip().lower()
        tenant_modules = normalize_tenant_modules(tenant.modules)
        if module not in tenant_modules:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Module disabled")
        if user.role == models.UserRole.owner:
            return tenant
        if not user.group_id:
            return tenant

        group = (
            db.query(models.UserGroup)
            .filter(models.UserGroup.id == user.group_id)
            .first()
        )
        if group is not None and not group.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Group disabled")

        permissions = user_group_permissions(db, user)
        if not permission_allows_action(permissions, module, action_key):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
        return tenant

    return dependency
