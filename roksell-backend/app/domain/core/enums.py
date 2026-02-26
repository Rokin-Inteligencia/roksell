import enum


class OrderStatus(enum.Enum):
    received = "received"
    confirmed = "confirmed"
    preparing = "preparing"
    ready = "ready"
    on_route = "on_route"
    delivered = "delivered"
    completed = "completed"
    canceled = "canceled"


class PaymentMethod(enum.Enum):
    pix = "pix"
    cash = "cash"


class PaymentStatus(enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    canceled = "canceled"


class DeliveryStatus(enum.Enum):
    pending = "pending"
    on_route = "on_route"
    delivered = "delivered"
    canceled = "canceled"


class TenantStatus(enum.Enum):
    active = "active"
    suspended = "suspended"
    canceled = "canceled"


class UserRole(enum.Enum):
    owner = "owner"
    manager = "manager"
    operator = "operator"


class CampaignType(enum.Enum):
    order_percent = "order_percent"
    shipping_percent = "shipping_percent"
    category_percent = "category_percent"
    rule = "rule"
