from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/holzlinge.db"
    admin_user: str | None = None
    admin_password: str | None = None
    session_idle_hours: int = 12
    shopify_store: str | None = None
    shopify_client_id: str | None = None
    shopify_client_secret: str | None = None
    shopify_admin_token: str | None = None
    shopify_api_version: str = "2026-01"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.1-flash-lite"


settings = Settings()
