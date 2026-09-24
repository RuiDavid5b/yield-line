"""
Centralized, typed application settings. Instantiate once (module-level
`settings` below) and import that instance elsewhere.
"""

from functools import lru_cache

from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database / infrastructure
    database_url: PostgresDsn
    redis_url: RedisDsn
    aws_region: str

    # Cognito
    cognito_client_id: str
    cognito_user_pool_id: str

    # External APIs
    edgar_user_agent: str
    google_api_key: str = ""
    currents_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
