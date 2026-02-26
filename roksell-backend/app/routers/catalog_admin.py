import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import asc, func, or_
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.auth.dependencies import require_module_action, require_roles
from app.db import get_db
from app.domain.catalog.availability import (
    block_sale_from_status,
    normalize_availability_status,
    resolve_availability_status,
)
from app.domain.tenancy.access import user_accessible_store_ids
from app.storage import build_media_key, storage_delete_by_url, storage_save
from app.tenancy import TenantContext

router = APIRouter(prefix="/admin/catalog", tags=["admin-catalog"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_VIDEO_TYPES = {
    "video/mp4": "mp4",
    "video/webm": "webm",
}
MAX_VIDEO_BYTES = 20 * 1024 * 1024

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xFF\xD8\xFF"
RIFF_SIGNATURE = b"RIFF"
WEBP_SIGNATURE = b"WEBP"
WEBM_SIGNATURE = b"\x1A\x45\xDF\xA3"
CANCELED_ORDER_STATUSES = ("canceled", "cancelado", "cancelada", "cancelled")


def _load_accessible_store_ids(db: Session, tenant_id: str, user: models.User) -> list[str]:
    store_ids = user_accessible_store_ids(db=db, tenant_id=tenant_id, user=user)
    if not store_ids:
        raise HTTPException(status_code=403, detail="No store access")
    return store_ids


def _with_global_store_scope(store_column, allowed_store_ids: list[str]):
    return or_(store_column.in_(allowed_store_ids), store_column.is_(None))


def _resolve_store_id_for_write(
    db: Session,
    tenant_id: str,
    user: models.User,
    requested_store_id: str | None,
) -> str:
    allowed_store_ids = _load_accessible_store_ids(db, tenant_id, user)
    if requested_store_id:
        if requested_store_id not in allowed_store_ids:
            raise HTTPException(status_code=403, detail="Store access denied")
        return requested_store_id
    if len(allowed_store_ids) == 1:
        return allowed_store_ids[0]
    raise HTTPException(status_code=400, detail="store_id is required")


def _resolve_store_id_for_read(
    db: Session,
    tenant_id: str,
    user: models.User,
    requested_store_id: str | None,
) -> str:
    allowed_store_ids = _load_accessible_store_ids(db, tenant_id, user)
    if requested_store_id:
        if requested_store_id not in allowed_store_ids:
            raise HTTPException(status_code=403, detail="Store access denied")
        return requested_store_id
    return allowed_store_ids[0]


def _ensure_store_exists(db: Session, tenant_id: str, store_id: str) -> None:
    exists = (
        db.query(models.Store)
        .filter(models.Store.id == store_id, models.Store.tenant_id == tenant_id)
        .first()
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Store not found")


def _ensure_category_in_store(db: Session, tenant_id: str, category_id: str, store_id: str) -> None:
    category = (
        db.query(models.Category)
        .filter(
            models.Category.id == category_id,
            models.Category.tenant_id == tenant_id,
            models.Category.store_id == store_id,
        )
        .first()
    )
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category for store")


def _load_additional_rows_for_store(
    db: Session,
    tenant_id: str,
    store_id: str,
    additional_ids: list[str],
) -> dict[str, models.Additional]:
    ids = [item.strip() for item in additional_ids if item and item.strip()]
    if not ids:
        return {}
    unique_ids = sorted(set(ids))
    rows = (
        db.query(models.Additional)
        .filter(
            models.Additional.tenant_id == tenant_id,
            models.Additional.store_id == store_id,
            models.Additional.id.in_(unique_ids),
        )
        .all()
    )
    by_id = {row.id: row for row in rows}
    missing = [item for item in unique_ids if item not in by_id]
    if missing:
        raise HTTPException(status_code=400, detail=f"Invalid additional for store: {missing[0]}")
    return by_id


def _sync_product_additionals(
    db: Session,
    tenant_id: str,
    product: models.Product,
    target_store_id: str,
    requested_additional_ids: list[str],
) -> None:
    requested_ids = sorted(set(item.strip() for item in requested_additional_ids if item and item.strip()))
    _load_additional_rows_for_store(db, tenant_id, target_store_id, requested_ids)

    current_links = (
        db.query(models.ProductAdditional)
        .filter(
            models.ProductAdditional.tenant_id == tenant_id,
            models.ProductAdditional.product_id == product.id,
        )
        .all()
    )
    current_ids = {link.additional_id for link in current_links}
    requested_id_set = set(requested_ids)

    for link in current_links:
        if link.additional_id not in requested_id_set:
            db.delete(link)

    for additional_id in requested_id_set - current_ids:
        db.add(
            models.ProductAdditional(
                tenant_id=tenant_id,
                product_id=product.id,
                additional_id=additional_id,
            )
        )


def _drop_invalid_product_additionals_for_store(
    db: Session,
    tenant_id: str,
    product: models.Product,
    target_store_id: str,
) -> None:
    valid_ids = {
        row[0]
        for row in db.query(models.Additional.id).filter(
            models.Additional.tenant_id == tenant_id,
            models.Additional.store_id == target_store_id,
        )
    }
    for link in list(product.additional_links):
        if link.additional_id not in valid_ids:
            db.delete(link)


def _has_non_canceled_sales_for_products(db: Session, tenant_id: str, product_ids: list[str]) -> bool:
    ids = [item for item in product_ids if item]
    if not ids:
        return False
    canceled_status = func.lower(func.coalesce(models.Order.status, ""))
    is_canceled = or_(
        canceled_status.in_(CANCELED_ORDER_STATUSES),
        canceled_status.like("%cancel%"),
    )
    row = (
        db.query(models.OrderItem.id)
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .filter(
            models.OrderItem.tenant_id == tenant_id,
            models.OrderItem.product_id.in_(ids),
            ~is_canceled,
        )
        .first()
    )
    return row is not None


def _has_sales_using_additional(
    db: Session,
    tenant_id: str,
    additional_name: str,
) -> bool:
    normalized_name = (additional_name or "").strip()
    if not normalized_name:
        return False
    row = (
        db.query(models.OrderItem.id)
        .filter(
            models.OrderItem.tenant_id == tenant_id,
            models.OrderItem.notes.isnot(None),
            models.OrderItem.notes.ilike("%Adicionais:%"),
            models.OrderItem.notes.ilike(f"%{normalized_name}%"),
        )
        .first()
    )
    return row is not None


def _resolve_store_media_segment(db: Session, tenant_id: str, store_id: str | None) -> str:
    if not store_id:
        return "global"
    row = (
        db.query(models.Store.slug)
        .filter(models.Store.tenant_id == tenant_id, models.Store.id == store_id)
        .first()
    )
    slug = row[0] if row else None
    return slug or store_id


def _normalize_master_name(value: str | None) -> str:
    name = (value or "").strip()
    return name or "Produto"


def _load_product_master_or_400(db: Session, tenant_id: str, product_master_id: str) -> models.ProductMaster:
    master = (
        db.query(models.ProductMaster)
        .filter(
            models.ProductMaster.id == product_master_id,
            models.ProductMaster.tenant_id == tenant_id,
        )
        .first()
    )
    if not master:
        raise HTTPException(status_code=400, detail="Invalid product_master_id")
    return master


def _create_local_product_master(db: Session, tenant_id: str, name_canonical: str) -> models.ProductMaster:
    master = models.ProductMaster(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name_canonical=_normalize_master_name(name_canonical),
        is_shared=False,
    )
    db.add(master)
    db.flush()
    return master


@router.get("/product-masters", response_model=list[schemas.ProductMasterOut])
def list_product_masters(
    q: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "view")),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    query = db.query(models.ProductMaster).filter(models.ProductMaster.tenant_id == tenant.id)
    if q and q.strip():
        token = f"%{q.strip()}%"
        query = query.filter(models.ProductMaster.name_canonical.ilike(token))
    return query.order_by(asc(models.ProductMaster.name_canonical)).limit(limit).all()


@router.post("/product-masters", response_model=schemas.ProductMasterOut, status_code=201)
def create_product_master(
    payload: schemas.ProductMasterCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    name_canonical = _normalize_master_name(payload.name_canonical)
    sku_global = (payload.sku_global or "").strip() or None

    if sku_global:
        duplicated_sku = (
            db.query(models.ProductMaster.id)
            .filter(
                models.ProductMaster.tenant_id == tenant.id,
                models.ProductMaster.sku_global == sku_global,
            )
            .first()
        )
        if duplicated_sku:
            raise HTTPException(status_code=400, detail="sku_global already exists")

    master = models.ProductMaster(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        name_canonical=name_canonical,
        sku_global=sku_global,
        is_shared=payload.is_shared,
    )
    db.add(master)
    db.commit()
    db.refresh(master)
    return master


@router.post("/categories", response_model=schemas.CategoryOut, status_code=201)
def create_category(
    payload: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    target_store_id = _resolve_store_id_for_write(db, tenant.id, user, payload.store_id)
    _ensure_store_exists(db, tenant.id, target_store_id)

    exists = (
        db.query(models.Category)
        .filter(
            models.Category.tenant_id == tenant.id,
            models.Category.store_id == target_store_id,
            models.Category.name == payload.name,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Category already exists")

    category = models.Category(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        store_id=target_store_id,
        name=payload.name,
        is_active=payload.is_active,
        display_order=payload.display_order,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=schemas.CategoryOut)
def update_category(
    category_id: str,
    payload: schemas.CategoryUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    allowed_store_ids = _load_accessible_store_ids(db, tenant.id, user)
    category = (
        db.query(models.Category)
        .filter(
            models.Category.id == category_id,
            models.Category.tenant_id == tenant.id,
            _with_global_store_scope(models.Category.store_id, allowed_store_ids),
        )
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    target_store_id = category.store_id
    if payload.store_id is not None:
        target_store_id = _resolve_store_id_for_write(db, tenant.id, user, payload.store_id)

    next_name = payload.name if payload.name is not None else category.name
    duplicate = (
        db.query(models.Category)
        .filter(
            models.Category.tenant_id == tenant.id,
            models.Category.store_id == target_store_id,
            models.Category.name == next_name,
            models.Category.id != category.id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Category already exists")

    category.store_id = target_store_id
    if payload.name is not None:
        category.name = payload.name
    if payload.display_order is not None:
        category.display_order = payload.display_order
    if payload.is_active is not None:
        category.is_active = payload.is_active

    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    allowed_store_ids = _load_accessible_store_ids(db, tenant.id, user)
    category = (
        db.query(models.Category)
        .filter(
            models.Category.id == category_id,
            models.Category.tenant_id == tenant.id,
            _with_global_store_scope(models.Category.store_id, allowed_store_ids),
        )
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    category_product_ids = [
        row[0]
        for row in db.query(models.Product.id).filter(
            models.Product.tenant_id == tenant.id,
            models.Product.category_id == category.id,
        )
    ]
    if _has_non_canceled_sales_for_products(db, tenant.id, category_product_ids):
        raise HTTPException(
            status_code=400,
            detail="Nao foi possivel excluir a categoria: existem vendas vinculadas aos produtos desta categoria.",
        )
    db.delete(category)
    db.commit()


@router.get("/additionals", response_model=list[schemas.AdditionalOut])
def list_additionals(
    store_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "view")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    selected_store_id = _resolve_store_id_for_read(db, tenant.id, user, store_id)
    return (
        db.query(models.Additional)
        .filter(models.Additional.tenant_id == tenant.id, models.Additional.store_id == selected_store_id)
        .order_by(asc(models.Additional.display_order), asc(models.Additional.name))
        .all()
    )


@router.post("/additionals", response_model=schemas.AdditionalOut, status_code=201)
def create_additional(
    payload: schemas.AdditionalCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    target_store_id = _resolve_store_id_for_write(db, tenant.id, user, payload.store_id)
    _ensure_store_exists(db, tenant.id, target_store_id)
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    exists = (
        db.query(models.Additional.id)
        .filter(
            models.Additional.tenant_id == tenant.id,
            models.Additional.store_id == target_store_id,
            models.Additional.name == name,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Additional already exists")

    additional = models.Additional(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        store_id=target_store_id,
        name=name,
        description=payload.description,
        price_cents=payload.price_cents,
        is_active=payload.is_active,
        display_order=payload.display_order,
    )
    db.add(additional)
    db.commit()
    db.refresh(additional)
    return additional


@router.patch("/additionals/{additional_id}", response_model=schemas.AdditionalOut)
def update_additional(
    additional_id: str,
    payload: schemas.AdditionalUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    allowed_store_ids = _load_accessible_store_ids(db, tenant.id, user)
    additional = (
        db.query(models.Additional)
        .filter(
            models.Additional.id == additional_id,
            models.Additional.tenant_id == tenant.id,
            _with_global_store_scope(models.Additional.store_id, allowed_store_ids),
        )
        .first()
    )
    if not additional:
        raise HTTPException(status_code=404, detail="Additional not found")

    target_store_id = additional.store_id
    if payload.store_id is not None:
        target_store_id = _resolve_store_id_for_write(db, tenant.id, user, payload.store_id)
        if target_store_id != additional.store_id:
            linked = (
                db.query(models.ProductAdditional.product_id)
                .filter(
                    models.ProductAdditional.tenant_id == tenant.id,
                    models.ProductAdditional.additional_id == additional.id,
                )
                .first()
            )
            if linked:
                raise HTTPException(status_code=400, detail="Cannot change store of linked additional")

    next_name = (payload.name if payload.name is not None else additional.name).strip()
    if not next_name:
        raise HTTPException(status_code=400, detail="Name is required")

    duplicate = (
        db.query(models.Additional.id)
        .filter(
            models.Additional.tenant_id == tenant.id,
            models.Additional.store_id == target_store_id,
            models.Additional.name == next_name,
            models.Additional.id != additional.id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Additional already exists")

    additional.store_id = target_store_id
    additional.name = next_name
    if "description" in payload.model_fields_set:
        additional.description = payload.description
    if payload.price_cents is not None:
        additional.price_cents = payload.price_cents
    if payload.is_active is not None:
        additional.is_active = payload.is_active
    if payload.display_order is not None:
        additional.display_order = payload.display_order

    db.commit()
    db.refresh(additional)
    return additional


@router.delete("/additionals/{additional_id}", status_code=204)
def delete_additional(
    additional_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    allowed_store_ids = _load_accessible_store_ids(db, tenant.id, user)
    additional = (
        db.query(models.Additional)
        .filter(
            models.Additional.id == additional_id,
            models.Additional.tenant_id == tenant.id,
            _with_global_store_scope(models.Additional.store_id, allowed_store_ids),
        )
        .first()
    )
    if not additional:
        raise HTTPException(status_code=404, detail="Additional not found")

    if _has_sales_using_additional(db, tenant.id, additional.name):
        raise HTTPException(
            status_code=400,
            detail="Nao foi possivel excluir o adicional: ele ja possui historico de vendas.",
        )

    db.delete(additional)
    db.commit()


@router.post("/products", response_model=schemas.ProductOut, status_code=201)
def create_product(
    payload: schemas.ProductCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    target_store_id = _resolve_store_id_for_write(db, tenant.id, user, payload.store_id)
    _ensure_store_exists(db, tenant.id, target_store_id)

    if payload.category_id:
        _ensure_category_in_store(db, tenant.id, payload.category_id, target_store_id)

    if not payload.is_custom:
        if not payload.name or payload.price_cents is None:
            raise HTTPException(status_code=400, detail="Name and price are required")
    name = payload.name or "Produto customizado"
    price_cents = payload.price_cents if payload.price_cents is not None else 0
    try:
        availability_status = resolve_availability_status(payload.availability_status, payload.block_sale)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid availability_status")

    if payload.product_master_id:
        master = _load_product_master_or_400(db, tenant.id, payload.product_master_id)
    else:
        master = _create_local_product_master(db, tenant.id, name)

    product = models.Product(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        product_master_id=master.id,
        store_id=target_store_id,
        category_id=payload.category_id,
        name=name,
        description=payload.description,
        price_cents=price_cents,
        is_active=payload.is_active,
        is_custom=payload.is_custom,
        additionals_enabled=payload.additionals_enabled,
        block_sale=block_sale_from_status(availability_status),
        availability_status=availability_status,
        image_url=payload.image_url,
        video_url=payload.video_url,
        display_order=payload.display_order,
        tags=payload.tags,
    )
    db.add(product)
    _sync_product_additionals(
        db=db,
        tenant_id=tenant.id,
        product=product,
        target_store_id=target_store_id,
        requested_additional_ids=payload.additional_ids,
    )
    db.commit()
    db.refresh(product)
    return product


@router.patch("/products/{product_id}", response_model=schemas.ProductOut)
def update_product(
    product_id: str,
    payload: schemas.ProductUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    allowed_store_ids = _load_accessible_store_ids(db, tenant.id, user)
    product = (
        db.query(models.Product)
        .filter(
            models.Product.id == product_id,
            models.Product.tenant_id == tenant.id,
            _with_global_store_scope(models.Product.store_id, allowed_store_ids),
        )
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    target_store_id = product.store_id
    if payload.store_id is not None:
        target_store_id = _resolve_store_id_for_write(db, tenant.id, user, payload.store_id)
        if payload.category_id is None and product.category_id:
            same_store_category = (
                db.query(models.Category.id)
                .filter(
                    models.Category.id == product.category_id,
                    models.Category.tenant_id == tenant.id,
                    models.Category.store_id == target_store_id,
                )
                .first()
            )
            if same_store_category is None:
                product.category_id = None
        if "additional_ids" not in payload.model_fields_set:
            _drop_invalid_product_additionals_for_store(
                db=db,
                tenant_id=tenant.id,
                product=product,
                target_store_id=target_store_id,
            )

    if payload.category_id is not None:
        _ensure_category_in_store(db, tenant.id, payload.category_id, target_store_id)

    if payload.name is not None:
        product.name = payload.name
    if payload.description is not None:
        product.description = payload.description
    if payload.price_cents is not None:
        product.price_cents = payload.price_cents
    if payload.is_active is not None:
        product.is_active = payload.is_active
    if payload.is_custom is not None:
        product.is_custom = payload.is_custom
    if payload.additionals_enabled is not None:
        product.additionals_enabled = payload.additionals_enabled
    if payload.availability_status is not None or payload.block_sale is not None:
        try:
            if payload.availability_status is not None:
                availability_status = normalize_availability_status(payload.availability_status)
            else:
                availability_status = resolve_availability_status(None, payload.block_sale)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid availability_status")
        if availability_status is None:
            availability_status = "available"
        product.availability_status = availability_status
        product.block_sale = block_sale_from_status(availability_status)
    if "image_url" in payload.model_fields_set:
        if payload.image_url is None and product.image_url:
            storage_delete_by_url(product.image_url)
        product.image_url = payload.image_url
    if "video_url" in payload.model_fields_set:
        if payload.video_url is None and product.video_url:
            storage_delete_by_url(product.video_url)
        product.video_url = payload.video_url
    if payload.category_id is not None:
        product.category_id = payload.category_id
    if payload.display_order is not None:
        product.display_order = payload.display_order
    if payload.tags is not None:
        product.tags = payload.tags
    if "product_master_id" in payload.model_fields_set:
        if not payload.product_master_id:
            raise HTTPException(status_code=400, detail="product_master_id is required")
        master = _load_product_master_or_400(db, tenant.id, payload.product_master_id)
        product.product_master_id = master.id
    elif not product.product_master_id:
        # Keep backward compatibility for rows created before product masters existed.
        master = _create_local_product_master(db, tenant.id, product.name)
        product.product_master_id = master.id
    if "additional_ids" in payload.model_fields_set:
        if not target_store_id:
            raise HTTPException(status_code=400, detail="store_id is required to configure additionals")
        _sync_product_additionals(
            db=db,
            tenant_id=tenant.id,
            product=product,
            target_store_id=target_store_id,
            requested_additional_ids=payload.additional_ids or [],
        )

    product.store_id = target_store_id

    db.commit()
    db.refresh(product)
    return product


@router.post("/products/{product_id}/image", response_model=schemas.ProductOut)
def upload_product_image(
    product_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    allowed_store_ids = _load_accessible_store_ids(db, tenant.id, user)
    product = (
        db.query(models.Product)
        .filter(
            models.Product.id == product_id,
            models.Product.tenant_id == tenant.id,
            _with_global_store_scope(models.Product.store_id, allowed_store_ids),
        )
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    file_name = (file.filename or "").lower()
    expected_ext = ALLOWED_IMAGE_TYPES.get(file.content_type or "")
    if not expected_ext:
        if file_name.endswith(".jpg") or file_name.endswith(".jpeg"):
            expected_ext = "jpg"
        elif file_name.endswith(".png"):
            expected_ext = "png"
        elif file_name.endswith(".webp"):
            expected_ext = "webp"
    if not expected_ext:
        raise HTTPException(status_code=400, detail="Unsupported image type")

    contents = file.file.read(MAX_IMAGE_BYTES + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="Empty image file")
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

    detected_ext = None
    if contents.startswith(PNG_SIGNATURE):
        detected_ext = "png"
    elif contents.startswith(JPEG_SIGNATURE):
        detected_ext = "jpg"
    elif contents.startswith(RIFF_SIGNATURE) and contents[8:12] == WEBP_SIGNATURE:
        detected_ext = "webp"
    if detected_ext != expected_ext:
        raise HTTPException(status_code=400, detail="Invalid image file")

    ext = detected_ext
    filename = f"{uuid.uuid4()}.{ext}"
    store_segment = _resolve_store_media_segment(db, tenant.id, product.store_id)
    key = build_media_key("tenants", tenant.slug, "stores", store_segment, "products", product.id, filename)

    storage_delete_by_url(product.image_url)
    product.image_url = storage_save(key, contents, file.content_type)
    db.commit()
    db.refresh(product)
    return product


@router.post("/products/{product_id}/video", response_model=schemas.ProductOut)
def upload_product_video(
    product_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    allowed_store_ids = _load_accessible_store_ids(db, tenant.id, user)
    product = (
        db.query(models.Product)
        .filter(
            models.Product.id == product_id,
            models.Product.tenant_id == tenant.id,
            _with_global_store_scope(models.Product.store_id, allowed_store_ids),
        )
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    file_name = (file.filename or "").lower()
    expected_ext = ALLOWED_VIDEO_TYPES.get(file.content_type or "")
    if not expected_ext:
        if file_name.endswith(".mp4"):
            expected_ext = "mp4"
        elif file_name.endswith(".webm"):
            expected_ext = "webm"
    if not expected_ext:
        raise HTTPException(status_code=400, detail="Unsupported video type")

    contents = file.file.read(MAX_VIDEO_BYTES + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="Empty video file")
    if len(contents) > MAX_VIDEO_BYTES:
        raise HTTPException(status_code=400, detail="Video too large (max 20MB)")

    detected_ext = None
    if contents.startswith(WEBM_SIGNATURE):
        detected_ext = "webm"
    elif len(contents) >= 12 and contents[4:8] == b"ftyp":
        detected_ext = "mp4"
    if detected_ext != expected_ext:
        raise HTTPException(status_code=400, detail="Invalid video file")

    ext = detected_ext
    filename = f"{uuid.uuid4()}.{ext}"
    store_segment = _resolve_store_media_segment(db, tenant.id, product.store_id)
    key = build_media_key("tenants", tenant.slug, "stores", store_segment, "products", product.id, filename)

    storage_delete_by_url(product.video_url)
    product.video_url = storage_save(key, contents, file.content_type)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{product_id}", status_code=204)
def delete_product(
    product_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    allowed_store_ids = _load_accessible_store_ids(db, tenant.id, user)
    product = (
        db.query(models.Product)
        .filter(
            models.Product.id == product_id,
            models.Product.tenant_id == tenant.id,
            _with_global_store_scope(models.Product.store_id, allowed_store_ids),
        )
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if _has_non_canceled_sales_for_products(db, tenant.id, [product.id]):
        raise HTTPException(
            status_code=400,
            detail="Nao foi possivel excluir o produto: existem vendas vinculadas a este registro.",
        )
    storage_delete_by_url(product.image_url)
    storage_delete_by_url(product.video_url)
    db.delete(product)
    db.commit()


@router.get("", response_model=schemas.CatalogOut)
def get_admin_catalog(
    store_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "view")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    selected_store_id = _resolve_store_id_for_read(db, tenant.id, user, store_id)

    categories = (
        db.query(models.Category)
        .filter(
            models.Category.tenant_id == tenant.id,
            (models.Category.store_id == selected_store_id) | (models.Category.store_id.is_(None)),
        )
        .order_by(asc(models.Category.display_order), asc(models.Category.name))
        .all()
    )
    products = (
        db.query(models.Product)
        .options(selectinload(models.Product.additional_links))
        .filter(
            models.Product.tenant_id == tenant.id,
            (models.Product.store_id == selected_store_id) | (models.Product.store_id.is_(None)),
        )
        .order_by(
            asc(models.Product.category_id),
            asc(models.Product.display_order),
            asc(models.Product.name),
        )
        .all()
    )
    additionals = (
        db.query(models.Additional)
        .filter(
            models.Additional.tenant_id == tenant.id,
            or_(models.Additional.store_id == selected_store_id, models.Additional.store_id.is_(None)),
        )
        .order_by(
            asc(models.Additional.display_order),
            asc(models.Additional.name),
        )
        .all()
    )
    return {
        "categories": categories,
        "products": products,
        "additionals": additionals,
        "selected_store_id": selected_store_id,
    }

