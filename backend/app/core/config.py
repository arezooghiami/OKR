from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OKR_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://okr:okr_dev_password@localhost:5433/okr"
    secret_key: str = "dev-only-secret-change-me-0123456789abcdef"
    cors_origins: list[str] = ["http://localhost:5173"]
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    timezone: str = "Asia/Tehran"
    max_failed_logins: int = 5
    lockout_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
