"""
Router admin/catalog: orquestração HTTP e upload de arquivos.
Toda a lógica de negócio está em app.services.catalog_admin.
"""
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app import models, schemas
from app.auth.dependencies import require_module_action, require_roles
from app.db import get_db
from app.services import catalog_admin as catalog_admin_svc
from app.storage import build_media_key, storage_delete_by_url, storage_save
from app.tenancy import TenantContext
from sqlalchemy.orm import Session

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


@router.get("/product-masters", response_model=list[schemas.ProductMasterOut])
def list_product_masters(
    q: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "view")),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    return catalog_admin_svc.list_product_masters(db=db, tenant_id=tenant.id, q=q, limit=limit)


@router.post("/product-masters", response_model=schemas.ProductMasterOut, status_code=201)
def create_product_master(
    payload: schemas.ProductMasterCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    _: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    return catalog_admin_svc.create_product_master(db=db, tenant_id=tenant.id, payload=payload)


@router.post("/categories", response_model=schemas.CategoryOut, status_code=201)
def create_category(
    payload: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    return catalog_admin_svc.create_category(db=db, tenant_id=tenant.id, user=user, payload=payload)


@router.patch("/categories/{category_id}", response_model=schemas.CategoryOut)
def update_category(
    category_id: str,
    payload: schemas.CategoryUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    return catalog_admin_svc.update_category(
        db=db, tenant_id=tenant.id, user=user, category_id=category_id, payload=payload
    )


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    catalog_admin_svc.delete_category(db=db, tenant_id=tenant.id, user=user, category_id=category_id)


@router.get("/additionals", response_model=list[schemas.AdditionalOut])
def list_additionals(
    store_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "view")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    return catalog_admin_svc.list_additionals(db=db, tenant_id=tenant.id, user=user, store_id=store_id)


@router.post("/additionals", response_model=schemas.AdditionalOut, status_code=201)
def create_additional(
    payload: schemas.AdditionalCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    return catalog_admin_svc.create_additional(db=db, tenant_id=tenant.id, user=user, payload=payload)


@router.patch("/additionals/{additional_id}", response_model=schemas.AdditionalOut)
def update_additional(
    additional_id: str,
    payload: schemas.AdditionalUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    return catalog_admin_svc.update_additional(
        db=db, tenant_id=tenant.id, user=user, additional_id=additional_id, payload=payload
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
    if "image_url" in payload.model_fields_set:
        if payload.image_url is None and additional.image_url:
            storage_delete_by_url(additional.image_url)
        additional.image_url = payload.image_url

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

    storage_delete_by_url(additional.image_url)
    db.delete(additional)
    db.commit()


@router.post("/additionals/{additional_id}/image", response_model=schemas.AdditionalOut)
def upload_additional_image(
    additional_id: str,
    file: UploadFile = File(...),
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
    store_segment = catalog_admin_svc.resolve_store_media_segment(db, tenant.id, additional.store_id)
    key = build_media_key("tenants", tenant.slug, "stores", store_segment, "additionals", additional.id, filename)

    storage_delete_by_url(additional.image_url)
    additional.image_url = storage_save(key, contents, file.content_type)
    db.commit()
    db.refresh(additional)
    return additional


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
        image_urls=payload.image_urls,
        video_url=payload.video_url,
        video_position=(payload.video_position or "end")[:10],
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
    return catalog_admin_svc.update_product(
        db=db, tenant_id=tenant.id, user=user, product_id=product_id, payload=payload
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
    if "image_urls" in payload.model_fields_set:
        old_urls = product.image_urls or []
        new_urls = payload.image_urls or []
        for u in old_urls:
            if u and u not in new_urls:
                storage_delete_by_url(u)
        product.image_urls = new_urls[:5]  # max 5
        product.image_url = new_urls[0] if new_urls else None
    if "video_url" in payload.model_fields_set:
        if payload.video_url is None and product.video_url:
            storage_delete_by_url(product.video_url)
        product.video_url = payload.video_url
    if payload.video_position is not None:
        product.video_position = payload.video_position[:10]
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


def _validate_image_upload(file: UploadFile, contents: bytes) -> str:
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

    return detected_ext


def _validate_video_upload(file: UploadFile, contents: bytes) -> str:
    file_name = (file.filename or "").lower()
    expected_ext = ALLOWED_VIDEO_TYPES.get(file.content_type or "")
    if not expected_ext:
        if file_name.endswith(".mp4"):
            expected_ext = "mp4"
        elif file_name.endswith(".webm"):
            expected_ext = "webm"
    if not expected_ext:
        raise HTTPException(status_code=400, detail="Unsupported video type")
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
    return detected_ext


@router.post("/products/{product_id}/image", response_model=schemas.ProductOut)
def upload_product_image(
    product_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    product = catalog_admin_svc.get_product_for_edit(db=db, tenant_id=tenant.id, user=user, product_id=product_id)
    contents = file.file.read(MAX_IMAGE_BYTES + 1)
    ext = _validate_image_upload(file, contents)
    filename = f"{uuid.uuid4()}.{ext}"
    store_segment = catalog_admin_svc.resolve_store_media_segment(db, tenant.id, product.store_id)
    key = build_media_key("tenants", tenant.slug, "stores", store_segment, "products", product.id, filename)
    storage_delete_by_url(product.image_url)
    url = storage_save(key, contents, file.content_type)
    return catalog_admin_svc.update_product_media_url(
        db=db, tenant_id=tenant.id, user=user, product_id=product_id, field="image_url", url=url
    )


@router.post("/products/{product_id}/video", response_model=schemas.ProductOut)
def upload_product_video(
    product_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    product = catalog_admin_svc.get_product_for_edit(db=db, tenant_id=tenant.id, user=user, product_id=product_id)
    contents = file.file.read(MAX_VIDEO_BYTES + 1)
    ext = _validate_video_upload(file, contents)
    filename = f"{uuid.uuid4()}.{ext}"
    store_segment = catalog_admin_svc.resolve_store_media_segment(db, tenant.id, product.store_id)
    key = build_media_key("tenants", tenant.slug, "stores", store_segment, "products", product.id, filename)
    storage_delete_by_url(product.video_url)
    url = storage_save(key, contents, file.content_type)
    return catalog_admin_svc.update_product_media_url(
        db=db, tenant_id=tenant.id, user=user, product_id=product_id, field="video_url", url=url
    )


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
    for url in product.image_urls or []:
        storage_delete_by_url(url)
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
    return catalog_admin_svc.get_catalog_for_admin(
        db=db,
        tenant_id=tenant.id,
        user=user,
        store_id=store_id,
    )
