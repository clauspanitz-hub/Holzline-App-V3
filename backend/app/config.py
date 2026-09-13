from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_gemini_model(value: str | None) -> str:
    """AI-Studio-Anzeigenamen („Gemini 3.1 Flash Lite“) → API-ID."""
    raw = (value or "").strip() or "gemini-3.1-flash-lite"
    if " " in raw or raw != raw.casefold():
        return raw.casefold().replace(" ", "-")
    return raw


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
    imap_host: str | None = None
    imap_port: int = 993
    imap_user: str | None = None
    imap_password: str | None = None
    imap_folder: str = "INBOX"
    imap_processed_folder: str = "verarbeitet"
    imap_poll_hours: float = 6.0

    @field_validator("gemini_model", mode="before")
    @classmethod
    def _gemini_model_id(cls, value: object) -> str:
        return normalize_gemini_model(None if value is None else str(value))


settings = Settings()
