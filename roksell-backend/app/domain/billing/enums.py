import enum


class PlanInterval(enum.Enum):
    monthly = "monthly"
    yearly = "yearly"


class SubscriptionStatus(enum.Enum):
    trialing = "trialing"
    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    suspended = "suspended"
