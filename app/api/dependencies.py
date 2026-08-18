from functools import lru_cache
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_api_key(provided_key: str | None, expected_key: str) -> None:
    if not provided_key or not compare_digest(provided_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "ApiKey"},
        )


def require_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> None:
    validate_api_key(x_api_key, settings.app_api_key.get_secret_value())
