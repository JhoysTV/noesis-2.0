from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Noesis del Caribe"
    app_env: str = Field(default="production", alias="APP_ENV")
    app_base_url: str = Field(default="http://127.0.0.1:8000", alias="APP_BASE_URL")
    allowed_origins: str = Field(default="http://127.0.0.1:8000,http://localhost:8000", alias="ALLOWED_ORIGINS")

    database_path: str = Field(default="backend/data/noesis.sqlite3", alias="DATABASE_PATH")

    stripe_secret_key: str = Field(default="", alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field(default="", alias="STRIPE_WEBHOOK_SECRET")
    stripe_currency: str = Field(default="dop", alias="STRIPE_CURRENCY")

    studio_email: str = Field(default="info@noesisdelcaribe.com", alias="STUDIO_EMAIL")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(default="", alias="SMTP_FROM_EMAIL")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")

    admin_token: str = Field(default="", alias="ADMIN_TOKEN")

    @property
    def root_dir(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def database_file(self) -> Path:
        path = Path(self.database_path)
        if not path.is_absolute():
            path = self.root_dir / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_from_email)


@lru_cache
def get_settings() -> Settings:
    return Settings()
