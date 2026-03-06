"""
Serviço de catálogo admin: CRUD de product masters, categorias, adicionais e produtos.
O router admin/catalog apenas orquestra (HTTP, UploadFile, Depends) e chama este serviço.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import asc, func, or_
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.domain.catalog.availability import (
    block_sale_from_status,
    normalize_availability_status,
    resolve_availability_status,
)
from app.domain.tenancy.access import user_accessible_store_ids
from app.storage import storage_delete_by_url

CANCELED_ORDER_STATUSES = ("canceled", "cancelado", "cancelada", "cancelled")


def load_accessible_store_ids(db: Session, tenant_id: str, user: models.User) -> list[str]:
    store_ids = user_accessible_store_ids(db=db, tenant_id=tenant_id, user=user)
    if not store_ids:
        raise HTTPException(status_code=403, detail="No store access")
    return store_ids


def _with_global_store_scope(store_column, allowed_store_ids: list[str]):
    return or_(store_column.in_(allowed_store_ids), store_column.is_(None))


def resolve_store_id_for_write(
    db: Session,
    tenant_id: str,
    user: models.User,
    requested_store_id: str | None,
) -> str:
    allowed_store_ids = load_accessible_store_ids(db, tenant_id, user)
    if requested_store_id:
        if requested_store_id not in allowed_store_ids:
            raise HTTPException(status_code=403, detail="Store access denied")
        return requested_store_id
    if len(allowed_store_ids) == 1:
        return allowed_store_ids[0]
    raise HTTPException(status_code=400, detail="store_id is required")


def resolve_store_id_for_read(
    db: Session,
    tenant_id: str,
    user: models.User,
    requested_store_id: str | None,
) -> str:
    allowed_store_ids = load_accessible_store_ids(db, tenant_id, user)
    if requested_store_id:
        if requested_store_id not in allowed_store_ids:
            raise HTTPException(status_code=403, detail="Store access denied")
        return requested_store_id
    return allowed_store_ids[0]


def ensure_store_exists(db: Session, tenant_id: str, store_id: str) -> None:
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


def resolve_store_media_segment(db: Session, tenant_id: str, store_id: str | None) -> str:
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


# --- API pública ---


def get_catalog_for_admin(
    db: Session,
    tenant_id: str,
    user: models.User,
    store_id: str | None,
) -> dict:
    """Retorna categorias, produtos e adicionais para o admin do catálogo (GET "")."""
    selected_store_id = resolve_store_id_for_read(db, tenant_id, user, store_id)

    categories = (
        db.query(models.Category)
        .filter(
            models.Category.tenant_id == tenant_id,
            (models.Category.store_id == selected_store_id) | (models.Category.store_id.is_(None)),
        )
        .order_by(asc(models.Category.display_order), asc(models.Category.name))
        .all()
    )
    products = (
        db.query(models.Product)
        .options(selectinload(models.Product.additional_links))
        .filter(
            models.Product.tenant_id == tenant_id,
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
            models.Additional.tenant_id == tenant_id,
            or_(models.Additional.store_id == selected_store_id, models.Additional.store_id.is_(None)),
        )
        .order_by(asc(models.Additional.display_order), asc(models.Additional.name))
        .all()
    )
    return {
        "categories": categories,
        "products": products,
        "additionals": additionals,
        "selected_store_id": selected_store_id,
    }


def list_product_masters(
    db: Session,
    tenant_id: str,
    q: str | None = None,
    limit: int = 200,
) -> list[models.ProductMaster]:
    query = db.query(models.ProductMaster).filter(models.ProductMaster.tenant_id == tenant_id)
    if q and q.strip():
        token = f"%{q.strip()}%"
        query = query.filter(models.ProductMaster.name_canonical.ilike(token))
    return query.order_by(asc(models.ProductMaster.name_canonical)).limit(limit).all()


def create_product_master(
    db: Session,
    tenant_id: str,
    payload: schemas.ProductMasterCreate,
) -> models.ProductMaster:
    name_canonical = _normalize_master_name(payload.name_canonical)
    sku_global = (payload.sku_global or "").strip() or None

    if sku_global:
        duplicated_sku = (
            db.query(models.ProductMaster.id)
            .filter(
                models.ProductMaster.tenant_id == tenant_id,
                models.ProductMaster.sku_global == sku_global,
            )
            .first()
        )
        if duplicated_sku:
            raise HTTPException(status_code=400, detail="sku_global already exists")

    master = models.ProductMaster(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name_canonical=name_canonical,
        sku_global=sku_global,
        is_shared=payload.is_shared,
    )
    db.add(master)
    db.commit()
    db.refresh(master)
    return master


def create_category(
    db: Session,
    tenant_id: str,
    user: models.User,
    payload: schemas.CategoryCreate,
) -> models.Category:
    target_store_id = resolve_store_id_for_write(db, tenant_id, user, payload.store_id)
    ensure_store_exists(db, tenant_id, target_store_id)

    exists = (
        db.query(models.Category)
        .filter(
            models.Category.tenant_id == tenant_id,
            models.Category.store_id == target_store_id,
            models.Category.name == payload.name,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Category already exists")

    category = models.Category(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        store_id=target_store_id,
        name=payload.name,
        is_active=payload.is_active,
        display_order=payload.display_order,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(
    db: Session,
    tenant_id: str,
    user: models.User,
    category_id: str,
    payload: schemas.CategoryUpdate,
) -> models.Category:
    allowed_store_ids = load_accessible_store_ids(db, tenant_id, user)
    category = (
        db.query(models.Category)
        .filter(
            models.Category.id == category_id,
            models.Category.tenant_id == tenant_id,
            _with_global_store_scope(models.Category.store_id, allowed_store_ids),
        )
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    target_store_id = category.store_id
    if payload.store_id is not None:
        target_store_id = resolve_store_id_for_write(db, tenant_id, user, payload.store_id)

    next_name = payload.name if payload.name is not None else category.name
    duplicate = (
        db.query(models.Category)
        .filter(
            models.Category.tenant_id == tenant_id,
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


def delete_category(
    db: Session,
    tenant_id: str,
    user: models.User,
    category_id: str,
) -> None:
    allowed_store_ids = load_accessible_store_ids(db, tenant_id, user)
    category = (
        db.query(models.Category)
        .filter(
            models.Category.id == category_id,
            models.Category.tenant_id == tenant_id,
            _with_global_store_scope(models.Category.store_id, allowed_store_ids),
        )
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    category_product_ids = [
        row[0]
        for row in db.query(models.Product.id).filter(
            models.Product.tenant_id == tenant_id,
            models.Product.category_id == category.id,
        )
    ]
    if _has_non_canceled_sales_for_products(db, tenant_id, category_product_ids):
        raise HTTPException(
            status_code=400,
            detail="Nao foi possivel excluir a categoria: existem vendas vinculadas aos produtos desta categoria.",
        )
    db.delete(category)
    db.commit()


def list_additionals(
    db: Session,
    tenant_id: str,
    user: models.User,
    store_id: str | None,
) -> list[models.Additional]:
    selected_store_id = resolve_store_id_for_read(db, tenant_id, user, store_id)
    return (
        db.query(models.Additional)
        .filter(models.Additional.tenant_id == tenant_id, models.Additional.store_id == selected_store_id)
        .order_by(asc(models.Additional.display_order), asc(models.Additional.name))
        .all()
    )


def create_additional(
    db: Session,
    tenant_id: str,
    user: models.User,
    payload: schemas.AdditionalCreate,
) -> models.Additional:
    target_store_id = resolve_store_id_for_write(db, tenant_id, user, payload.store_id)
    ensure_store_exists(db, tenant_id, target_store_id)
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    exists = (
        db.query(models.Additional.id)
        .filter(
            models.Additional.tenant_id == tenant_id,
            models.Additional.store_id == target_store_id,
            models.Additional.name == name,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Additional already exists")

    additional = models.Additional(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
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


def update_additional(
    db: Session,
    tenant_id: str,
    user: models.User,
    additional_id: str,
    payload: schemas.AdditionalUpdate,
) -> models.Additional:
    allowed_store_ids = load_accessible_store_ids(db, tenant_id, user)
    additional = (
        db.query(models.Additional)
        .filter(
            models.Additional.id == additional_id,
            models.Additional.tenant_id == tenant_id,
            _with_global_store_scope(models.Additional.store_id, allowed_store_ids),
        )
        .first()
    )
    if not additional:
        raise HTTPException(status_code=404, detail="Additional not found")

    target_store_id = additional.store_id
    if payload.store_id is not None:
        target_store_id = resolve_store_id_for_write(db, tenant_id, user, payload.store_id)
        if target_store_id != additional.store_id:
            linked = (
                db.query(models.ProductAdditional.product_id)
                .filter(
                    models.ProductAdditional.tenant_id == tenant_id,
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
            models.Additional.tenant_id == tenant_id,
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


def delete_additional(
    db: Session,
    tenant_id: str,
    user: models.User,
    additional_id: str,
) -> None:
    allowed_store_ids = load_accessible_store_ids(db, tenant_id, user)
    additional = (
        db.query(models.Additional)
        .filter(
            models.Additional.id == additional_id,
            models.Additional.tenant_id == tenant_id,
            _with_global_store_scope(models.Additional.store_id, allowed_store_ids),
        )
        .first()
    )
    if not additional:
        raise HTTPException(status_code=404, detail="Additional not found")

    if _has_sales_using_additional(db, tenant_id, additional.name):
        raise HTTPException(
            status_code=400,
            detail="Nao foi possivel excluir o adicional: ele ja possui historico de vendas.",
        )

    db.delete(additional)
    db.commit()


def create_product(
    db: Session,
    tenant_id: str,
    user: models.User,
    payload: schemas.ProductCreate,
) -> models.Product:
    target_store_id = resolve_store_id_for_write(db, tenant_id, user, payload.store_id)
    ensure_store_exists(db, tenant_id, target_store_id)

    if payload.category_id:
        _ensure_category_in_store(db, tenant_id, payload.category_id, target_store_id)

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
        master = _load_product_master_or_400(db, tenant_id, payload.product_master_id)
    else:
        master = _create_local_product_master(db, tenant_id, name)

    product = models.Product(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
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
        tenant_id=tenant_id,
        product=product,
        target_store_id=target_store_id,
        requested_additional_ids=payload.additional_ids,
    )
    db.commit()
    db.refresh(product)
    return product


def update_product(
    db: Session,
    tenant_id: str,
    user: models.User,
    product_id: str,
    payload: schemas.ProductUpdate,
) -> models.Product:
    allowed_store_ids = load_accessible_store_ids(db, tenant_id, user)
    product = (
        db.query(models.Product)
        .filter(
            models.Product.id == product_id,
            models.Product.tenant_id == tenant_id,
            _with_global_store_scope(models.Product.store_id, allowed_store_ids),
        )
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    target_store_id = product.store_id
    if payload.store_id is not None:
        target_store_id = resolve_store_id_for_write(db, tenant_id, user, payload.store_id)
        if payload.category_id is None and product.category_id:
            same_store_category = (
                db.query(models.Category.id)
                .filter(
                    models.Category.id == product.category_id,
                    models.Category.tenant_id == tenant_id,
                    models.Category.store_id == target_store_id,
                )
                .first()
            )
            if same_store_category is None:
                product.category_id = None
        if "additional_ids" not in payload.model_fields_set:
            _drop_invalid_product_additionals_for_store(
                db=db,
                tenant_id=tenant_id,
                product=product,
                target_store_id=target_store_id,
            )

    if payload.category_id is not None:
        _ensure_category_in_store(db, tenant_id, payload.category_id, target_store_id)

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
        master = _load_product_master_or_400(db, tenant_id, payload.product_master_id)
        product.product_master_id = master.id
    elif not product.product_master_id:
        master = _create_local_product_master(db, tenant_id, product.name)
        product.product_master_id = master.id
    if "additional_ids" in payload.model_fields_set:
        if not target_store_id:
            raise HTTPException(status_code=400, detail="store_id is required to configure additionals")
        _sync_product_additionals(
            db=db,
            tenant_id=tenant_id,
            product=product,
            target_store_id=target_store_id,
            requested_additional_ids=payload.additional_ids or [],
        )

    product.store_id = target_store_id

    db.commit()
    db.refresh(product)
    return product


def delete_product(
    db: Session,
    tenant_id: str,
    user: models.User,
    product_id: str,
) -> None:
    allowed_store_ids = load_accessible_store_ids(db, tenant_id, user)
    product = (
        db.query(models.Product)
        .filter(
            models.Product.id == product_id,
            models.Product.tenant_id == tenant_id,
            _with_global_store_scope(models.Product.store_id, allowed_store_ids),
        )
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if _has_non_canceled_sales_for_products(db, tenant_id, [product.id]):
        raise HTTPException(
            status_code=400,
            detail="Nao foi possivel excluir o produto: existem vendas vinculadas a este registro.",
        )
    storage_delete_by_url(product.image_url)
    storage_delete_by_url(product.video_url)
    db.delete(product)
    db.commit()


def update_product_media_url(
    db: Session,
    tenant_id: str,
    user: models.User,
    product_id: str,
    field: str,
    url: str | None,
) -> models.Product:
    """Atualiza image_url ou video_url do produto após o router ter feito storage_save. field deve ser 'image_url' ou 'video_url'."""
    allowed_store_ids = load_accessible_store_ids(db, tenant_id, user)
    product = (
        db.query(models.Product)
        .filter(
            models.Product.id == product_id,
            models.Product.tenant_id == tenant_id,
            _with_global_store_scope(models.Product.store_id, allowed_store_ids),
        )
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if field == "image_url":
        product.image_url = url
    elif field == "video_url":
        product.video_url = url
    else:
        raise ValueError("field must be 'image_url' or 'video_url'")
    db.commit()
    db.refresh(product)
    return product


def get_product_for_edit(
    db: Session,
    tenant_id: str,
    user: models.User,
    product_id: str,
) -> models.Product:
    """Carrega produto para edição (ex.: upload de mídia). 404 se não existir ou sem acesso."""
    allowed_store_ids = load_accessible_store_ids(db, tenant_id, user)
    product = (
        db.query(models.Product)
        .filter(
            models.Product.id == product_id,
            models.Product.tenant_id == tenant_id,
            _with_global_store_scope(models.Product.store_id, allowed_store_ids),
        )
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
