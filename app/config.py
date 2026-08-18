from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    database_url: Annotated[SecretStr, Field(description="PostgreSQL connection string")]
    gemini_api_key: Annotated[SecretStr, Field(description="Gemini API key")]
    app_api_key: Annotated[
        SecretStr,
        Field(min_length=16, description="Shared key required by the REST API"),
    ]
    gemini_model: str = "gemini-3.6-flash"
    gemini_timeout_seconds: Annotated[float, Field(gt=0, le=60)] = 8.0
    gemini_max_attempts: Annotated[int, Field(ge=1, le=2)] = 2
    max_message_chars: Annotated[int, Field(ge=1, le=5000)] = 5000
    max_body_bytes: Annotated[int, Field(ge=1024, le=65536)] = 16_384
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_url", "gemini_api_key", "app_api_key")
    @classmethod
    def reject_blank_secrets(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value().strip()
        if not secret:
            raise ValueError("configuration value must not be blank")
        return SecretStr(secret)
