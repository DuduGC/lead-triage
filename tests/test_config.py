import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_load_required_runtime_configuration(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://app:secret@localhost/leads")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("APP_API_KEY", "test-app-key-123456")

    settings = Settings()

    assert settings.database_url.get_secret_value().endswith("/leads")
    assert settings.gemini_api_key.get_secret_value() == "test-gemini-key"
    assert settings.app_api_key.get_secret_value() == "test-app-key-123456"
    assert settings.gemini_model == "gemini-3.6-flash"


def test_settings_reject_missing_required_secret(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://app:secret@localhost/leads")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("APP_API_KEY", "test-app-key-123456")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_reject_blank_secret(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://app:secret@localhost/leads")
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    monkeypatch.setenv("APP_API_KEY", "test-app-key-123456")

    with pytest.raises(ValidationError):
        Settings()
