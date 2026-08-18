import pytest
from fastapi import HTTPException

from app.api.dependencies import validate_api_key


def test_validate_api_key_accepts_exact_key():
    assert validate_api_key("app-key-123456789", "app-key-123456789") is None


@pytest.mark.parametrize("provided_key", [None, "", "wrong-key"])
def test_validate_api_key_rejects_missing_or_wrong_key(provided_key):
    with pytest.raises(HTTPException) as raised:
        validate_api_key(provided_key, "app-key-123456789")

    assert raised.value.status_code == 401
    assert "app-key-123456789" not in str(raised.value.detail)
