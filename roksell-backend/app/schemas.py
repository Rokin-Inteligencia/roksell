from datetime import datetime, date
from typing import List, Optional, Literal

from pydantic import BaseModel, EmailStr, Field
from app import models

AvailabilityStatus = Literal["available", "order", "unavailable"]


# Catalog


class ProductOut(BaseModel):
    id: str
    product_master_id: Optional[str] = None
    store_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price_cents: int
    is_active: bool
    is_custom: bool = False
    block_sale: bool = False
    availability_status: AvailabilityStatus = "available"
    additionals_enabled: bool = False
    additional_ids: List[str] = Field(default_factory=list)
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    category_id: Optional[str] = None
    display_order: int

    class Config:
        from_attributes = True


class CategoryOut(BaseModel):
    id: str
    store_id: Optional[str] = None
    name: str
    is_active: bool
    display_order: int

    class Config:
        from_attributes = True


class AdditionalOut(BaseModel):
    id: str
    store_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    price_cents: int
    is_active: bool
    display_order: int

    class Config:
        from_attributes = True


class CampaignBannerOut(BaseModel):
    id: str
    name: str
    banner_image_url: Optional[str] = None
    banner_link_url: Optional[str] = None
    banner_position: Optional[str] = None
    banner_popup: bool
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OperatingHoursDay(BaseModel):
    day: int = Field(ge=0, le=6)
    enabled: bool = False
    open: Optional[str] = None
    close: Optional[str] = None


class CatalogOut(BaseModel):
    categories: List[CategoryOut]
    products: List[ProductOut]
    additionals: List[AdditionalOut] = []
    campaign_banners: List[CampaignBannerOut] = []
    cover_image_url: Optional[str] = None
    operating_hours: List[OperatingHoursDay] = []
    is_open: Optional[bool] = None
    sla_minutes: Optional[int] = None
    delivery_enabled: Optional[bool] = None
    whatsapp_contact_phone: Optional[str] = None
    payment_methods: List[str] = []
    selected_store_id: Optional[str] = None
    selected_store_slug: Optional[str] = None
    selected_store_name: Optional[str] = None


# Stores


class StoreOut(BaseModel):
    id: str
    name: str
    slug: Optional[str] = None
    timezone: str = "America/Sao_Paulo"
    is_active: bool
    is_delivery: bool
    allow_preorder_when_closed: bool = True
    lat: float
    lon: float
    closed_dates: List[date] = []
    operating_hours: List[OperatingHoursDay] = []
    postal_code: Optional[str] = None
    street: Optional[str] = None
    number: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    complement: Optional[str] = None
    reference: Optional[str] = None
    phone: Optional[str] = None
    sla_minutes: int = 45
    cover_image_url: Optional[str] = None
    whatsapp_contact_phone: Optional[str] = None
    payment_methods: List[str] = []
    order_statuses: List[str] = []
    order_status_canceled_color: Optional[str] = None
    order_status_colors: Optional[dict[str, str]] = None
    order_final_statuses: List[str] = []
    shipping_method: Optional[str] = None
    shipping_fixed_fee_cents: int = 0

    class Config:
        from_attributes = True


class StoreAddressOut(BaseModel):
    id: str
    name: Optional[str] = None
    postal_code: Optional[str] = None
    street: Optional[str] = None
    number: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    complement: Optional[str] = None
    reference: Optional[str] = None

    class Config:
        from_attributes = True


class StoreCreate(BaseModel):
    name: str
    lat: float
    lon: float
    timezone: str = "America/Sao_Paulo"
    is_active: bool = True
    is_delivery: bool = True
    allow_preorder_when_closed: bool = True
    closed_dates: Optional[List[date]] = None
    operating_hours: Optional[List[OperatingHoursDay]] = None
    postal_code: Optional[str] = None
    street: Optional[str] = None
    number: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    complement: Optional[str] = None
    reference: Optional[str] = None
    phone: Optional[str] = None
    sla_minutes: int = 45
    cover_image_url: Optional[str] = None
    whatsapp_contact_phone: Optional[str] = None
    payment_methods: Optional[List[str]] = None
    order_statuses: Optional[List[str]] = None
    order_status_canceled_color: Optional[str] = None
    order_status_colors: Optional[dict[str, str]] = None
    order_final_statuses: Optional[List[str]] = None
    shipping_method: Optional[str] = None
    shipping_fixed_fee_cents: int = 0


class StoreUpdate(BaseModel):
    name: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None
    is_delivery: Optional[bool] = None
    allow_preorder_when_closed: Optional[bool] = None
    closed_dates: Optional[List[date]] = None
    operating_hours: Optional[List[OperatingHoursDay]] = None
    postal_code: Optional[str] = None
    street: Optional[str] = None
    number: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    complement: Optional[str] = None
    reference: Optional[str] = None
    phone: Optional[str] = None
    sla_minutes: Optional[int] = None
    cover_image_url: Optional[str] = None
    whatsapp_contact_phone: Optional[str] = None
    payment_methods: Optional[List[str]] = None
    order_statuses: Optional[List[str]] = None
    order_status_canceled_color: Optional[str] = None
    order_status_colors: Optional[dict[str, str]] = None
    order_final_statuses: Optional[List[str]] = None
    shipping_method: Optional[str] = None
    shipping_fixed_fee_cents: Optional[int] = None


class StoreInventoryOut(BaseModel):
    product_id: str
    store_id: str
    quantity: int
    product_name: Optional[str] = None


class StoreInventoryUpdate(BaseModel):
    store_id: str
    product_id: str
    quantity: int


# Checkout


class AddressIn(BaseModel):
    postal_code: str
    street: str
    number: str
    complement: Optional[str] = None
    district: Optional[str] = None
    city: str
    state: str
    reference: Optional[str] = None


class ItemIn(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)
    custom_name: Optional[str] = None
    custom_description: Optional[str] = None
    custom_weight: Optional[str] = None
    custom_price_cents: Optional[int] = Field(default=None, ge=0)
    additional_ids: List[str] = Field(default_factory=list)
    item_notes: Optional[str] = None


class PaymentIn(BaseModel):
    method: Literal["pix", "cash"]


class CheckoutIn(BaseModel):
    phone: str
    name: str
    pickup: bool
    preorder_confirmed: bool = False
    store_id: Optional[str] = None
    address: Optional[AddressIn] = None
    items: List[ItemIn]
    delivery_window_start: Optional[datetime] = None
    delivery_window_end: Optional[datetime] = None
    notes: Optional[str] = None
    payment: PaymentIn
    shipping_cents: Optional[int] = None
    coupon_code: Optional[str] = None
    delivery_date: Optional[date] = None


class CheckoutPreviewIn(BaseModel):
    items: List[ItemIn]
    pickup: bool
    store_id: Optional[str] = None
    shipping_cents: Optional[int] = None
    coupon_code: Optional[str] = None
    delivery_date: Optional[date] = None


class CheckoutPreviewOut(BaseModel):
    subtotal_cents: int
    shipping_cents: int
    discount_cents: int
    total_cents: int
    campaign: Optional["CampaignOut"] = None


class OrderSummaryOut(BaseModel):
    order_id: str
    total_cents: int
    tracking_token: Optional[str] = None


# Customers


class CustomerOut(BaseModel):
    id: str
    name: str
    phone: str
    origin_store_id: Optional[str] = None
    origin_store_name: Optional[str] = None
    is_active: bool
    birthday: Optional[date] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    birthday: Optional[date] = None
    is_active: Optional[bool] = None

    class Config:
        extra = "ignore"  # tolera campos que o frontend ainda envia (ex.: email)


# Campaigns


class CampaignOut(BaseModel):
    id: str
    name: str
    type: str
    value_percent: int
    coupon_code: Optional[str] = None
    category_id: Optional[str] = None
    min_order_cents: Optional[int] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: bool
    usage_limit: Optional[int] = None
    usage_count: int
    apply_mode: Optional[str] = None
    priority: Optional[int] = None
    rule_config: Optional[dict | str] = None
    store_ids: Optional[List[str]] = None
    banner_enabled: bool
    banner_position: Optional[str] = None
    banner_popup: bool
    banner_image_url: Optional[str] = None
    banner_link_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CampaignCreate(BaseModel):
    name: str
    type: str
    value_percent: int
    coupon_code: Optional[str] = None
    category_id: Optional[str] = None
    min_order_cents: Optional[int] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: bool = True
    usage_limit: Optional[int] = None
    apply_mode: Optional[str] = None
    priority: Optional[int] = None
    rule_config: Optional[dict] = None
    store_ids: Optional[List[str]] = None
    banner_enabled: bool = False
    banner_position: Optional[str] = None
    banner_popup: bool = False
    banner_image_url: Optional[str] = None
    banner_link_url: Optional[str] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    value_percent: Optional[int] = None
    coupon_code: Optional[str] = None
    category_id: Optional[str] = None
    min_order_cents: Optional[int] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    usage_limit: Optional[int] = None
    apply_mode: Optional[str] = None
    priority: Optional[int] = None
    rule_config: Optional[dict] = None
    store_ids: Optional[List[str]] = None
    banner_enabled: Optional[bool] = None
    banner_position: Optional[str] = None
    banner_popup: Optional[bool] = None
    banner_image_url: Optional[str] = None
    banner_link_url: Optional[str] = None

    class Config:
        extra = "ignore"


# Orders


class OrderItemOut(BaseModel):
    name: str
    product_id: str
    quantity: int
    unit_price_cents: int

    class Config:
        from_attributes = True


class PaymentOut(BaseModel):
    method: Optional[str] = None
    status: Optional[str] = None

    class Config:
        from_attributes = True


class DeliveryOut(BaseModel):
    status: str
    postal_code: Optional[str] = None
    street: Optional[str] = None
    number: Optional[str] = None
    complement: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    reference: Optional[str] = None

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: str
    status: str
    pickup: bool
    created_at: Optional[datetime] = None
    delivery_date: Optional[date] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    whatsapp_contact_phone: Optional[str] = None
    whatsapp_order_message: Optional[str] = None
    pix_key: Optional[str] = None
    notes: Optional[str] = None
    subtotal_cents: int
    shipping_cents: Optional[int] = None
    discount_cents: Optional[int] = None
    total_cents: int
    items: List[OrderItemOut]
    payment: Optional[PaymentOut] = None
    delivery: Optional[DeliveryOut] = None
    store_id: Optional[str] = None
    store: Optional[StoreAddressOut] = None

    class Config:
        from_attributes = True


class OrderListItem(BaseModel):
    id: str
    customer_name: str | None = None
    created_at: datetime
    delivery_date: Optional[date] = None
    status: str
    total_cents: int
    store_id: Optional[str] = None
    notes: Optional[str] = None


class OrdersSummaryOut(BaseModel):
    open_count: int
    revenue_today_cents: int
    orders_today: int


class OrdersStatusCountOut(BaseModel):
    status: str
    count: int


class OrdersStatusSummaryOut(BaseModel):
    items: List[OrdersStatusCountOut]


class WhatsAppLogOut(BaseModel):
    id: str
    order_id: Optional[str] = None
    to_phone: str
    message: Optional[str] = None
    status: str
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime


class WhatsAppInboundMessageOut(BaseModel):
    id: str
    from_phone: str
    provider_message_id: Optional[str] = None
    message_type: Optional[str] = None
    message_text: Optional[str] = None
    media_url: Optional[str] = None
    media_mime: Optional[str] = None
    received_at: datetime
    created_at: datetime


class WhatsAppConversationMessageOut(BaseModel):
    id: str
    direction: str
    phone: str
    message_type: Optional[str] = None
    message_text: Optional[str] = None
    media_url: Optional[str] = None
    media_mime: Optional[str] = None
    status: Optional[str] = None
    provider_message_id: Optional[str] = None
    created_at: datetime


class WhatsAppUnreadOut(BaseModel):
    count: int


class WhatsAppThreadOut(BaseModel):
    phone: str
    customer_name: Optional[str] = None
    last_message: str
    last_received_at: datetime
    total: int
    unread_count: int = 0


class WhatsAppSendIn(BaseModel):
    phone: str
    text: str


class WhatsAppSendOut(BaseModel):
    ok: bool


class WebPushKeysIn(BaseModel):
    p256dh: str
    auth: str


class WhatsAppPushSubscriptionIn(BaseModel):
    endpoint: str
    keys: WebPushKeysIn
    expirationTime: Optional[datetime | int | float] = None
    user_agent: Optional[str] = None


class WhatsAppPushSubscriptionRemoveIn(BaseModel):
    endpoint: str


class WhatsAppPushPublicKeyOut(BaseModel):
    enabled: bool
    public_key: Optional[str] = None


class OrderItemUpdate(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


class OrderAdminUpdate(BaseModel):
    customer_id: Optional[str] = None
    items: Optional[List[OrderItemUpdate]] = None
    delivery_date: Optional[date] = None
    received_date: Optional[date] = None


# Auth


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_active: bool
    max_active_sessions: int = 3
    group_id: Optional[str] = None
    default_store_id: Optional[str] = None

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    tenant_id: str
    tenant_slug: str
    expires_in_seconds: int
    expires_at: datetime


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default=models.UserRole.operator.value)
    group_id: str
    max_active_sessions: int = Field(default=3, ge=1, le=20)
    default_store_id: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    email: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)
    role: Optional[str] = None
    group_id: Optional[str] = None
    is_active: Optional[bool] = None
    max_active_sessions: Optional[int] = Field(default=None, ge=1, le=20)
    default_store_id: Optional[str] = None


class UserLicensesOut(BaseModel):
    limit: int
    used: int


class TenantInfoOut(BaseModel):
    id: str
    slug: str
    name: str
    users_limit: int


# Admin onboarding


class OnboardingAddressOut(BaseModel):
    postal_code: str = ""
    street: str = ""
    number: str = ""
    district: str = ""
    city: str = ""
    state: str = ""
    complement: str = ""
    reference: str = ""


class OnboardingStateOut(BaseModel):
    needs_onboarding: bool
    store_id: Optional[str] = None
    store_name: str = ""
    person_type: str = "company"
    document: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    address: OnboardingAddressOut
    operating_hours: List[OperatingHoursDay] = Field(default_factory=list)


class OnboardingCompletePayload(BaseModel):
    store_id: Optional[str] = None
    store_name: str = Field(min_length=1, max_length=255)
    person_type: str = Field(min_length=1, max_length=32)
    document: str = Field(min_length=1, max_length=32)
    contact_email: EmailStr
    contact_phone: str = Field(min_length=1, max_length=32)
    postal_code: str = Field(min_length=8, max_length=16)
    street: str = Field(min_length=1, max_length=255)
    number: str = Field(min_length=1, max_length=32)
    district: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=255)
    state: str = Field(min_length=2, max_length=8)
    complement: Optional[str] = None
    reference: Optional[str] = None
    operating_hours: List[OperatingHoursDay] = Field(default_factory=list)


class OnboardingCompleteOut(BaseModel):
    ok: bool
    store_id: str


class OnboardingTestModeOut(BaseModel):
    ok: bool
    activation_mode: str


# Catalog admin


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1)
    store_id: Optional[str] = None
    is_active: bool = True
    display_order: int = 0


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    store_id: Optional[str] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class ProductCreate(BaseModel):
    name: Optional[str] = None
    product_master_id: Optional[str] = None
    store_id: Optional[str] = None
    description: Optional[str] = None
    price_cents: Optional[int] = None
    is_active: bool = True
    is_custom: bool = False
    additionals_enabled: bool = False
    additional_ids: List[str] = Field(default_factory=list)
    block_sale: bool = False
    availability_status: Optional[AvailabilityStatus] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    category_id: Optional[str] = None
    display_order: int = 0
    tags: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    product_master_id: Optional[str] = None
    store_id: Optional[str] = None
    description: Optional[str] = None
    price_cents: Optional[int] = None
    is_active: Optional[bool] = None
    is_custom: Optional[bool] = None
    additionals_enabled: Optional[bool] = None
    additional_ids: Optional[List[str]] = None
    block_sale: Optional[bool] = None
    availability_status: Optional[AvailabilityStatus] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    category_id: Optional[str] = None
    display_order: Optional[int] = None
    tags: Optional[str] = None


class OperationsConfigUpdate(BaseModel):
    sla_minutes: Optional[int] = None
    delivery_enabled: Optional[bool] = None
    cover_image_url: Optional[str] = None
    whatsapp_contact_phone: Optional[str] = None
    whatsapp_order_message: Optional[str] = None
    whatsapp_status_message: Optional[str] = None
    pix_key: Optional[str] = None
    order_statuses: Optional[List[str]] = None
    order_status_canceled_color: Optional[str] = None
    order_status_colors: Optional[dict[str, str]] = None
    order_final_statuses: Optional[List[str]] = None
    operating_hours: Optional[List[OperatingHoursDay]] = None
    payment_methods: Optional[List[str]] = None
    shipping_method: Optional[str] = None


class ProductMasterOut(BaseModel):
    id: str
    name_canonical: str
    sku_global: Optional[str] = None
    is_shared: bool

    class Config:
        from_attributes = True


class ProductMasterCreate(BaseModel):
    name_canonical: str = Field(min_length=1)
    sku_global: Optional[str] = None
    is_shared: bool = True


class AdditionalCreate(BaseModel):
    name: str = Field(min_length=1)
    store_id: Optional[str] = None
    description: Optional[str] = None
    price_cents: int = Field(default=0, ge=0)
    is_active: bool = True
    display_order: int = 0


class AdditionalUpdate(BaseModel):
    name: Optional[str] = None
    store_id: Optional[str] = None
    description: Optional[str] = None
    price_cents: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class ShippingDistanceTierIn(BaseModel):
    km_min: float
    km_max: float
    amount_cents: int


class ShippingDistanceTierOut(BaseModel):
    km_min: float
    km_max: float
    amount_cents: int


class PlanOut(BaseModel):
    id: str
    name: str
    price_cents: int
    currency: str
    interval: str
    description: Optional[str] = None
    modules: List[str] = Field(default_factory=list)


class SubscriptionOut(BaseModel):
    id: str
    plan_id: str
    status: str
    started_at: datetime
    current_period_end: Optional[datetime] = None
    modules: List[str] = Field(default_factory=list)


class GroupOut(BaseModel):
    id: str
    name: str
    is_active: bool
    permissions: List[str] = Field(default_factory=list)
    store_ids: List[str] = Field(default_factory=list)
    users_count: int = 0


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    permissions: List[str] = Field(default_factory=list)
    store_ids: Optional[List[str]] = None
    is_active: bool = True


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    permissions: Optional[List[str]] = None
    store_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None


class GroupStoreOptionOut(BaseModel):
    id: str
    name: str
    slug: Optional[str] = None


class GroupOptionsOut(BaseModel):
    modules: List[str] = Field(default_factory=list)
    stores: List[GroupStoreOptionOut] = Field(default_factory=list)
    active_plan_name: Optional[str] = None
    active_plan_id: Optional[str] = None


# Insights
class InsightBreakdownItem(BaseModel):
    name: str
    revenue_cents: int


class InsightAverageItem(BaseModel):
    name: str
    avg_cents: int
    avg_including_zero_cents: int
    total_cents: int
    days_with_sales: int
    total_days: int


class InsightsOut(BaseModel):
    revenue_today_cents: int
    revenue_week_cents: int
    revenue_month_cents: int
    by_category: List[InsightBreakdownItem]
    by_store: List[InsightBreakdownItem] = []
    by_product: List[InsightBreakdownItem]
    revenue_range_cents: int
    revenue_by_month: List[InsightBreakdownItem]
    by_product_quantity: List[InsightBreakdownItem]
    top_customers: List[InsightBreakdownItem] = []
    avg_by_weekday: List[InsightAverageItem] = []
    avg_by_week_of_month: List[InsightAverageItem] = []
    total_quantity: int
    total_orders: int
    orders_today: int
    orders_month: int
