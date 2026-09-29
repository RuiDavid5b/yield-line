"""
Centralized, typed application settings. Instantiate once (module-level
`settings` below) and import that instance elsewhere.
"""

import os
from functools import lru_cache

import boto3
from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database / infrastructure
    database_url: PostgresDsn
    redis_url: RedisDsn
    aws_region: str

    cookie_domain: str | None = None
    frontend_origin: str = "http://localhost:5173"

    # Cognito
    cognito_client_id: str
    cognito_user_pool_id: str
    # KMS
    byok_kms_key_alias: str

    # External APIs
    edgar_user_agent: str
    google_api_key: str = ""
    currents_api_key: str = ""


def _settings_from_ssm() -> Settings:
    region = os.environ["AWS_REGION"]
    client = boto3.client("ssm", region_name=region)
    prefix = "/stock-news/"
    params = client.get_parameters_by_path(
        Path=prefix, Recursive=True, WithDecryption=True
    )
    values = {p["Name"].removeprefix(prefix): p["Value"] for p in params["Parameters"]}
    values["aws_region"] = region
    return Settings(**values)


@lru_cache
def get_settings() -> Settings:
    if os.environ.get("USE_SSM_CONFIG") == "true":
        return _settings_from_ssm()
    return Settings()
