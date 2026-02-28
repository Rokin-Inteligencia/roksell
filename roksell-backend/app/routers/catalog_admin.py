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


@router.delete("/additionals/{additional_id}", status_code=204)
def delete_additional(
    additional_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    catalog_admin_svc.delete_additional(db=db, tenant_id=tenant.id, user=user, additional_id=additional_id)


@router.post("/products", response_model=schemas.ProductOut, status_code=201)
def create_product(
    payload: schemas.ProductCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_module_action("products", "edit")),
    user: models.User = Depends(require_roles(models.UserRole.owner, models.UserRole.manager, models.UserRole.operator)),
):
    return catalog_admin_svc.create_product(db=db, tenant_id=tenant.id, user=user, payload=payload)


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
    catalog_admin_svc.delete_product(db=db, tenant_id=tenant.id, user=user, product_id=product_id)


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
