import os
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import SessionLocal
from app.security import hash_password
from app.services.subscriptions import assign_plan_to_tenant
from app.tenancy import legacy_tenant_id


def uid() -> str:
    return str(uuid.uuid4())


def get_or_create_category(db: Session, tenant_id: str, name: str, order: int) -> models.Category:
    category = db.scalar(
        select(models.Category).where(
            models.Category.tenant_id == tenant_id,
            models.Category.name == name,
        )
    )
    if category:
        category.display_order = order
        return category
    category = models.Category(id=uid(), tenant_id=tenant_id, name=name, display_order=order)
    db.add(category)
    db.flush()
    return category


def get_or_create_product(
    db: Session,
    tenant_id: str,
    category_id: str,
    name: str,
    price_cents: int,
    order: int,
    description: str | None = None,
    image_url: str | None = None,
    tags: str | None = None,
) -> models.Product:
    product = db.scalar(
        select(models.Product).where(
            models.Product.tenant_id == tenant_id,
            models.Product.name == name,
        )
    )
    if product:
        product.price_cents = price_cents
        product.display_order = order
        if description is not None:
            product.description = description
        if image_url is not None:
            product.image_url = image_url
        if tags is not None:
            product.tags = tags
        return product
    product = models.Product(
        id=uid(),
        tenant_id=tenant_id,
        category_id=category_id,
        name=name,
        description=description,
        price_cents=price_cents,
        is_active=True,
        tags=tags,
        display_order=order,
        image_url=image_url,
    )
    db.add(product)
    return product


def ensure_operations_config(db: Session, tenant_id: str, sla: int = 45, delivery_enabled: bool = True) -> models.OperationsConfig:
    config = (
        db.query(models.OperationsConfig)
        .filter(models.OperationsConfig.tenant_id == tenant_id)
        .first()
    )
    if config:
        config.sla_minutes = sla
        config.delivery_enabled = delivery_enabled
        return config
    config = models.OperationsConfig(tenant_id=tenant_id, sla_minutes=sla, delivery_enabled=delivery_enabled)
    db.add(config)
    return config


def ensure_shipping_tier(db: Session, tenant_id: str, km_min: float, km_max: float, amount_cents: int) -> models.ShippingDistanceTier:
    tier = (
        db.query(models.ShippingDistanceTier)
        .filter(
            models.ShippingDistanceTier.tenant_id == tenant_id,
            models.ShippingDistanceTier.km_min == km_min,
            models.ShippingDistanceTier.km_max == km_max,
        )
        .first()
    )
    if tier:
        tier.amount_cents = amount_cents
        return tier
    tier = models.ShippingDistanceTier(
        tenant_id=tenant_id,
        km_min=km_min,
        km_max=km_max,
        amount_cents=amount_cents,
    )
    db.add(tier)
    return tier


def ensure_module(db: Session, key: str, name: str, description: str | None = None) -> models.Module:
    module = (
        db.query(models.Module)
        .filter(models.Module.key == key)
        .first()
    )
    if module:
        module.name = name
        module.description = description
        module.is_active = True
        return module
    module = models.Module(id=uid(), key=key, name=name, description=description, is_active=True)
    db.add(module)
    db.flush()
    return module

def ensure_master_tenant(db: Session, tenant_id: str, name: str, slug: str) -> models.Tenant:
    normalized_slug = slug.strip().lower()
    tenant = db.scalar(select(models.Tenant).where(models.Tenant.id == tenant_id))
    if tenant:
        tenant.name = name
        if normalized_slug:
            tenant.slug = normalized_slug
        return tenant

    tenant = models.Tenant(
        id=tenant_id,
        name=name,
        slug=normalized_slug or "legacy",
        status=models.TenantStatus.active,
    )
    db.add(tenant)
    db.flush()
    return tenant

def ensure_plan(db: Session, name: str, price_cents: int, interval: models.PlanInterval, module_keys: list[str]) -> models.Plan:
    plan = (
        db.query(models.Plan)
        .filter(models.Plan.name == name)
        .first()
    )
    if plan:
        plan.price_cents = price_cents
        plan.interval = interval
        plan.is_active = True
    else:
        plan = models.Plan(
            id=uid(),
            name=name,
            price_cents=price_cents,
            interval=interval,
            is_active=True,
        )
        db.add(plan)
        db.flush()

    db.query(models.PlanModule).filter(models.PlanModule.plan_id == plan.id).delete()
    modules = (
        db.query(models.Module)
        .filter(models.Module.key.in_(module_keys))
        .all()
    )
    modules_by_key = {m.key: m for m in modules}
    for key in module_keys:
        mod = modules_by_key.get(key)
        if not mod:
            continue
        db.add(models.PlanModule(plan_id=plan.id, module_id=mod.id))
    db.flush()
    return plan


def main() -> None:
    tenant_id = legacy_tenant_id()
    db: Session = SessionLocal()
    try:
        master_name = os.getenv("DEFAULT_TENANT_NAME", "Rokin")
        master_slug = os.getenv("DEFAULT_TENANT_SLUG", "rokin")
        ensure_master_tenant(db, tenant_id, name=master_name, slug=master_slug)

        cat_promo = get_or_create_category(db, tenant_id, "Weekly Specials", 1)
        cat_classics = get_or_create_category(db, tenant_id, "Classics", 2)
        cat_special = get_or_create_category(db, tenant_id, "Specials", 3)
        cat_light = get_or_create_category(db, tenant_id, "Light", 4)

        get_or_create_product(
            db, tenant_id, cat_classics.id, "Nero Assoluto", 800, 3,
            description="Dark dough with semi-sweet chocolate."
        )
        get_or_create_product(
            db, tenant_id, cat_classics.id, "Ciocco Bianco", 800, 4,
            description="Dark dough with white chocolate."
        )
        get_or_create_product(
            db, tenant_id, cat_classics.id, "Bacio Doppio", 800, 5,
            description="Dark dough with semi-sweet and white chocolate."
        )
        get_or_create_product(
            db, tenant_id, cat_special.id, "Nutelletto", 1000, 7,
            description="Traditional dough with semi-sweet chocolate and Nutella filling."
        )
        get_or_create_product(
            db, tenant_id, cat_special.id, "Velvetto", 1200, 8,
            description="Red dough with white chocolate and brigadeiro."
        )
        get_or_create_product(
            db, tenant_id, cat_special.id, "Cappuccino", 1200, 9,
            description="Dark dough with coffee and chocolate."
        )
        get_or_create_product(
            db, tenant_id, cat_light.id, "Castagno", 1200, 10,
            description="Sugar-free dough with 60% chocolate."
        )
        get_or_create_product(
            db, tenant_id, cat_light.id, "Amaro", 1400, 11,
            description="Sugar-free dough with nuts and 60% chocolate."
        )

        ensure_shipping_tier(db, tenant_id, 0, 5, 1500)
        ensure_shipping_tier(db, tenant_id, 5, 10, 2500)

        ensure_operations_config(db, tenant_id, sla=45, delivery_enabled=True)

        mod_online_orders = ensure_module(
            db,
            key="online_orders",
            name="Online Orders",
            description="Web checkout and status tracking.",
        )
        mod_delivery = ensure_module(
            db,
            key="delivery",
            name="Delivery Management",
            description="Shipping calculator and courier tracking.",
        )

        starter_plan = ensure_plan(
            db,
            name="Starter",
            price_cents=9900,
            interval=models.PlanInterval.monthly,
            module_keys=[mod_online_orders.key, mod_delivery.key],
        )

        assign_plan_to_tenant(db, tenant_id, starter_plan.id)

        default_admin_email = os.getenv("DEFAULT_ADMIN_EMAIL")
        default_admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD")
        if default_admin_email and default_admin_password:
            ensure_admin_user(
                db,
                tenant_id,
                email=default_admin_email,
                password=default_admin_password,
                name=os.getenv("DEFAULT_ADMIN_NAME", "Administrator"),
            )

        db.commit()
        print("Seed OK")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
def ensure_admin_user(db: Session, tenant_id: str, email: str, password: str, name: str = "Administrator") -> models.User:
    normalized = email.strip().lower()
    user = (
        db.query(models.User)
        .filter(
            models.User.tenant_id == tenant_id,
            models.User.email == normalized,
        )
        .first()
    )
    if user:
        return user
    user = models.User(
        id=uid(),
        tenant_id=tenant_id,
        name=name,
        email=normalized,
        password_hash=hash_password(password),
        role=models.UserRole.owner,
    )
    db.add(user)
    return user


def ensure_module(db: Session, key: str, name: str, description: str | None = None) -> models.Module:
    module = (
        db.query(models.Module)
        .filter(models.Module.key == key)
        .first()
    )
    if module:
        module.name = name
        module.description = description
        module.is_active = True
        return module
    module = models.Module(id=uid(), key=key, name=name, description=description, is_active=True)
    db.add(module)
    db.flush()
    return module


def ensure_plan(db: Session, name: str, price_cents: int, interval: models.PlanInterval, module_keys: list[str]) -> models.Plan:
    plan = (
        db.query(models.Plan)
        .filter(models.Plan.name == name)
        .first()
    )
    if plan:
        plan.price_cents = price_cents
        plan.interval = interval
        plan.is_active = True
    else:
        plan = models.Plan(
            id=uid(),
            name=name,
            price_cents=price_cents,
            interval=interval,
            is_active=True,
        )
        db.add(plan)
        db.flush()

    db.query(models.PlanModule).filter(models.PlanModule.plan_id == plan.id).delete()
    modules = (
        db.query(models.Module)
        .filter(models.Module.key.in_(module_keys))
        .all()
    )
    modules_by_key = {m.key: m for m in modules}
    for key in module_keys:
        mod = modules_by_key.get(key)
        if not mod:
            continue
        db.add(models.PlanModule(plan_id=plan.id, module_id=mod.id))
    db.flush()
    return plan
