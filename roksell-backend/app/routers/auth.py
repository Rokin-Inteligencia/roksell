import uuid
from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import get_current_user
from app.db import get_db, settings
from app.domain.tenancy.access import dump_json_list, normalize_tenant_modules
from app.security import create_access_token, hash_password, verify_password
from app.services.user_sessions import create_user_session, revoke_user_session
from app.tenancy import TenantContext, build_tenant_context, get_tenant_context, resolve_tenant

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _session_ttl_minutes() -> int:
    configured = int(getattr(settings, "admin_session_expire_minutes", 480) or 480)
    return max(5, configured)


def _token_response(
    user: models.User,
    tenant: TenantContext,
    *,
    session_id: str,
    expires_at: datetime,
) -> schemas.TokenOut:
    expires_minutes = _session_ttl_minutes()
    token = create_access_token(
        {
            "sub": user.id,
            "tenant_id": tenant.id,
            "role": user.role.value,
            "sid": session_id,
        },
        expires_minutes=expires_minutes,
    )
    return schemas.TokenOut(
        access_token=token,
        user=user,
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        expires_in_seconds=expires_minutes * 60,
        expires_at=expires_at,
    )


def _set_auth_cookie(response: Response, token: str, *, max_age_seconds: int):
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=max_age_seconds,
        path="/",
    )


def _extract_token(
    authorization: str | None,
    token_cookie: str | None,
) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    if token_cookie:
        return token_cookie
    return None


def _decode_token_payload(token: str) -> dict | None:
    for secret in settings.AUTH_SECRETS_LIST:
        try:
            return jwt.decode(token, secret, algorithms=[settings.auth_algorithm])
        except JWTError:
            continue
    return None


@router.post("/signup", response_model=schemas.TokenOut, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupPayload,
    response: Response,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    email = _normalize_email(payload.email)
    existing = (
        db.query(models.User)
        .filter(
            models.User.tenant_id == tenant.id,
            func.lower(models.User.email) == email,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    user_count = db.query(models.User).filter(models.User.tenant_id == tenant.id).count()
    if user_count > 0:
        raise HTTPException(status_code=403, detail="Use the admin portal to invite new users")

    group = (
        db.query(models.UserGroup)
        .filter(models.UserGroup.tenant_id == tenant.id)
        .order_by(models.UserGroup.created_at.asc())
        .first()
    )
    if group is None:
        group = models.UserGroup(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            name="Administradores",
            permissions_json=dump_json_list(sorted(normalize_tenant_modules(tenant.modules))),
            store_ids_json=None,
            is_active=True,
        )
        db.add(group)
        db.flush()

    user = models.User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        group_id=group.id,
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=models.UserRole.owner,
    )
    db.add(user)
    session_id, expires_at = create_user_session(
        db,
        user=user,
        tenant_id=tenant.id,
        ttl_minutes=_session_ttl_minutes(),
    )
    db.commit()
    db.refresh(user)
    token = _token_response(user, tenant, session_id=session_id, expires_at=expires_at)
    _set_auth_cookie(response, token.access_token, max_age_seconds=token.expires_in_seconds)
    return token


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
    token_cookie: str | None = Cookie(default=None, alias="admin_token"),
):
    token = _extract_token(authorization, token_cookie)
    if token:
        payload = _decode_token_payload(token)
        if payload:
            user_id = payload.get("sub")
            tenant_id = payload.get("tenant_id")
            session_id = payload.get("sid")
            if user_id and tenant_id and session_id:
                revoke_user_session(
                    db,
                    user_id=str(user_id),
                    tenant_id=str(tenant_id),
                    session_id=str(session_id),
                    reason="logout",
                )
                db.commit()
    response.delete_cookie("admin_token", path="/")
    return {"ok": True}


@router.post("/login", response_model=schemas.TokenOut)
def login(
    payload: LoginPayload,
    response: Response,
    db: Session = Depends(get_db),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_tenant: str | None = Header(default=None, alias="X-Tenant"),
):
    email = _normalize_email(payload.email)
    tenant_context: TenantContext | None = None
    user: models.User | None = None
    if x_tenant_id or x_tenant:
        tenant_model = resolve_tenant(db, tenant_id=x_tenant_id, tenant_slug=x_tenant)
        if tenant_model is None:
            raise HTTPException(status_code=404, detail="Tenant nao encontrado")
        tenant_context = build_tenant_context(db, tenant_model)
        user = (
            db.query(models.User)
            .filter(
                models.User.tenant_id == tenant_context.id,
                func.lower(models.User.email) == email,
            )
            .first()
        )
    else:
        users = (
            db.query(models.User)
            .filter(func.lower(models.User.email) == email)
            .all()
        )
        if not users:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if len(users) > 1:
            raise HTTPException(status_code=409, detail="Multiple tenants for this email")
        user = users[0]
        tenant_model = db.query(models.Tenant).filter(models.Tenant.id == user.tenant_id).first()
        if tenant_model is None:
            raise HTTPException(status_code=404, detail="Tenant nao encontrado")
        tenant_context = build_tenant_context(db, tenant_model)

    if not user or not verify_password(payload.password, user.password_hash) or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    session_id, expires_at = create_user_session(
        db,
        user=user,
        tenant_id=tenant_context.id,
        ttl_minutes=_session_ttl_minutes(),
    )
    db.commit()
    db.refresh(user)
    token = _token_response(user, tenant_context, session_id=session_id, expires_at=expires_at)
    _set_auth_cookie(response, token.access_token, max_age_seconds=token.expires_in_seconds)
    return token
