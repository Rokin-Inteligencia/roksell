from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    database_url: str = Field(alias="DATABASE_URL")

    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, alias="TELEGRAM_CHAT_ID")
    whatsapp_token: str | None = Field(default=None, alias="WHATSAPP_TOKEN")
    whatsapp_phone_number_id: str | None = Field(default=None, alias="WHATSAPP_PHONE_NUMBER_ID")
    auth_secret: str = Field(alias="AUTH_SECRET")
    auth_secret_previous: str | None = Field(default=None, alias="AUTH_SECRET_PREVIOUS")
    auth_secrets: str | None = Field(default=None, alias="AUTH_SECRETS")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    admin_session_expire_minutes: int = Field(default=480, alias="ADMIN_SESSION_EXPIRE_MINUTES")
    auth_algorithm: str = Field(default="HS256", alias="AUTH_ALGORITHM")
    billing_webhook_secret: str | None = Field(default=None, alias="BILLING_WEBHOOK_SECRET")
    billing_webhook_secrets: str | None = Field(default=None, alias="BILLING_WEBHOOK_SECRETS")
    order_tracking_secret: str | None = Field(default=None, alias="ORDER_TRACKING_SECRET")

    # Config do pydantic-settings (v2)
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",        # ignora chaves do .env que não tenham campo/alias
        case_sensitive=False,  # tolera caixa; prefira MAIÚSCULO no .env
    )

    # Propriedades p/ compatibilidade (caso alguém use MAIÚSCULO em outro lugar)
    @property
    def DATABASE_URL(self) -> str:
        return self.database_url

    @property
    def TELEGRAM_BOT_TOKEN(self) -> str | None:
        return self.telegram_bot_token

    @property
    def TELEGRAM_CHAT_ID(self) -> str | None:
        return self.telegram_chat_id

    @property
    def WHATSAPP_TOKEN(self) -> str | None:
        return self.whatsapp_token

    @property
    def WHATSAPP_PHONE_NUMBER_ID(self) -> str | None:
        return self.whatsapp_phone_number_id

    @property
    def AUTH_SECRET(self) -> str:
        return self.auth_secret

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return self.access_token_expire_minutes

    @property
    def ADMIN_SESSION_EXPIRE_MINUTES(self) -> int:
        return self.admin_session_expire_minutes

    @property
    def AUTH_ALGORITHM(self) -> str:
        return self.auth_algorithm

    @property
    def AUTH_SECRETS_LIST(self) -> list[str]:
        secrets = [self.auth_secret]
        if self.auth_secret_previous:
            secrets.append(self.auth_secret_previous)
        if self.auth_secrets:
            secrets.extend([s.strip() for s in self.auth_secrets.split(",") if s.strip()])
        unique: list[str] = []
        for secret in secrets:
            if secret not in unique:
                unique.append(secret)
        return unique

    @property
    def BILLING_WEBHOOK_SECRET(self) -> str | None:
        return self.billing_webhook_secret

    @property
    def BILLING_WEBHOOK_SECRETS_LIST(self) -> list[str]:
        secrets: list[str] = []
        if self.billing_webhook_secret:
            secrets.append(self.billing_webhook_secret)
        if self.billing_webhook_secrets:
            secrets.extend([s.strip() for s in self.billing_webhook_secrets.split(",") if s.strip()])
        unique: list[str] = []
        for secret in secrets:
            if secret not in unique:
                unique.append(secret)
        return unique

    @property
    def ORDER_TRACKING_SECRET(self) -> str | None:
        return self.order_tracking_secret

    @field_validator("auth_secret")
    @classmethod
    def validate_auth_secret(cls, value: str) -> str:
        if not value or value == "change-me" or len(value) < 32:
            raise ValueError("AUTH_SECRET must be set and at least 32 chars long")
        return value

    @field_validator("auth_secret_previous")
    @classmethod
    def validate_auth_secret_previous(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value == "change-me" or len(value) < 32:
            raise ValueError("AUTH_SECRET_PREVIOUS must be at least 32 chars long")
        return value

    @field_validator("auth_secrets")
    @classmethod
    def validate_auth_secrets(cls, value: str | None) -> str | None:
        if value is None:
            return value
        secrets = [s.strip() for s in value.split(",") if s.strip()]
        for secret in secrets:
            if secret == "change-me" or len(secret) < 32:
                raise ValueError("AUTH_SECRETS entries must be at least 32 chars long")
        return value

    @field_validator("billing_webhook_secret")
    @classmethod
    def validate_billing_webhook_secret(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if len(value) < 32:
            raise ValueError("BILLING_WEBHOOK_SECRET must be at least 32 chars long")
        return value

    @field_validator("billing_webhook_secrets")
    @classmethod
    def validate_billing_webhook_secrets(cls, value: str | None) -> str | None:
        if value is None:
            return value
        secrets = [s.strip() for s in value.split(",") if s.strip()]
        for secret in secrets:
            if len(secret) < 32:
                raise ValueError("BILLING_WEBHOOK_SECRETS entries must be at least 32 chars long")
        return value


settings = Settings()

# use a property minúscula (ou a maiúscula de compatibilidade, ambas funcionam)
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
