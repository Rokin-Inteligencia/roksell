import json
import re
import unicodedata

from sqlalchemy.orm import Session

from app import models

MANDATORY_MODULE_KEYS = frozenset({"config", "customers", "products"})
MODULE_PERMISSION_ACTIONS = frozenset({"view", "edit"})


def load_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for item in data:
        cleaned = str(item or "").strip()
        if cleaned and cleaned not in out:
            out.append(cleaned)
    return out


def dump_json_list(values: list[str]) -> str | None:
    unique: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    if not unique:
        return None
    return json.dumps(unique)


def normalize_store_slug(value: str) -> str:
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "loja"


def ensure_unique_store_slug(
    db: Session,
    tenant_id: str,
    desired_slug: str,
    exclude_store_id: str | None = None,
) -> str:
    base = normalize_store_slug(desired_slug)
    if not base:
        base = "loja"
    candidate = base
    suffix = 2
    while True:
        query = (
            db.query(models.Store.id)
            .filter(
                models.Store.tenant_id == tenant_id,
                models.Store.slug == candidate,
            )
        )
        if exclude_store_id:
            query = query.filter(models.Store.id != exclude_store_id)
        exists = query.first() is not None
        if not exists:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def _group_for_user(db: Session, user: models.User | None) -> models.UserGroup | None:
    if not user or not user.group_id:
        return None
    return db.query(models.UserGroup).filter(models.UserGroup.id == user.group_id).first()


def user_group_permissions(db: Session, user: models.User | None) -> set[str]:
    group = _group_for_user(db, user)
    return set(load_json_list(group.permissions_json if group else None))


def user_allowed_modules(
    *,
    db: Session,
    user: models.User | None,
    tenant_modules: set[str] | frozenset[str] | list[str],
) -> set[str]:
    tenant_module_set = normalize_tenant_modules(tenant_modules)
    if not user:
        return tenant_module_set
    if user.role == models.UserRole.owner:
        return tenant_module_set
    group = _group_for_user(db, user)
    if group is None:
        return tenant_module_set
    if not group.is_active:
        return set()
    group_permissions = user_group_permissions(db, user)
    permission_modules = modules_from_permissions(group_permissions)
    return tenant_module_set.intersection(permission_modules)


def normalize_tenant_modules(modules: set[str] | frozenset[str] | list[str]) -> set[str]:
    normalized = {str(item).strip() for item in modules if str(item).strip()}
    normalized.update(MANDATORY_MODULE_KEYS)
    return normalized


def split_module_permission(permission: str) -> tuple[str, str | None]:
    cleaned = str(permission or "").strip().lower()
    if not cleaned:
        return "", None
    module_key, sep, action = cleaned.partition(":")
    if not module_key:
        return "", None
    if not sep:
        return module_key, None
    action_value = action.strip().lower()
    if not action_value:
        return module_key, None
    return module_key, action_value


def modules_from_permissions(permissions: set[str] | list[str]) -> set[str]:
    modules: set[str] = set()
    for raw in permissions:
        module_key, action = split_module_permission(raw)
        if not module_key:
            continue
        if action is None or action in MODULE_PERMISSION_ACTIONS:
            modules.add(module_key)
    return modules


def permission_allows_action(
    permissions: set[str] | list[str],
    module_key: str,
    action: str,
) -> bool:
    module_value = (module_key or "").strip().lower()
    action_value = (action or "").strip().lower()
    if not module_value or action_value not in MODULE_PERMISSION_ACTIONS:
        return False

    permission_set = {str(item).strip().lower() for item in permissions if str(item).strip()}
    if module_value in permission_set:
        return True
    if f"{module_value}:edit" in permission_set:
        return True
    if action_value == "view" and f"{module_value}:view" in permission_set:
        return True
    return False


def user_accessible_store_ids(
    *,
    db: Session,
    tenant_id: str,
    user: models.User | None,
) -> list[str]:
    all_store_rows = (
        db.query(models.Store.id)
        .filter(models.Store.tenant_id == tenant_id)
        .order_by(models.Store.name.asc())
        .all()
    )
    all_store_ids = [row[0] for row in all_store_rows]
    if not user:
        return all_store_ids
    if user.role == models.UserRole.owner:
        return all_store_ids

    group = _group_for_user(db, user)
    if group:
        if not group.is_active:
            return []
        configured_ids = set(load_json_list(group.store_ids_json))
        if configured_ids:
            return [store_id for store_id in all_store_ids if store_id in configured_ids]

    if user.default_store_id and user.default_store_id in all_store_ids:
        return [user.default_store_id]
    return all_store_ids
