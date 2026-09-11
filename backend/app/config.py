from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/holzlinge.db"
    admin_user: str | None = None
    admin_password: str | None = None
    session_idle_hours: int = 12


settings = Settings()
