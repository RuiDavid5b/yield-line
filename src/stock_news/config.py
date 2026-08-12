"""
Centralized, typed application settings. Instantiate once (module-level
`settings` below) and import that instance elsewhere.
"""

from functools import lru_cache

from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: PostgresDsn
    redis_url: RedisDsn
    edgar_user_agent: str
    google_api_key: str = ""
    currents_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
