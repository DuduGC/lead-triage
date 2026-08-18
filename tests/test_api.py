import asyncio

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.integrations.gemini import ExtractionOutcome, GeminiExtraction, ReviewReason
from app.main import create_app
from app.persistence.models import Base
from app.services.lead_service import LeadService

MESSAGE = "Olá, sou Carlos da Loja ABC. Precisamos comprar 15 computadores ainda este mês."
API_KEY = "app-key-for-tests-123"


def extraction_payload() -> GeminiExtraction:
    return GeminiExtraction.model_validate(
        {
            "nome": "Carlos",
            "empresa": "Loja ABC",
            "produto_interesse": "computadores",
            "quantidade": 15,
            "prazo": "este mês",
            "intencao": "comprar",
            "urgencia": "alta",
            "evidencias": {
                "nome": "Carlos",
                "empresa": "Loja ABC",
                "produto_interesse": "computadores",
                "quantidade": "15",
                "prazo": "este mês",
                "intencao": "comprar",
                "urgencia": "este mês",
            },
        }
    )


class FakeExtractor:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = 0

    def extract(self, message: str):
        self.calls += 1
        return self.outcome


@pytest.fixture
def api_context():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    extractor = FakeExtractor(ExtractionOutcome(extraction_payload(), None))
    service = LeadService(session_factory=session_factory, extractor=extractor)
    settings = Settings(
        database_url="sqlite:///:memory:",
        gemini_api_key="local-test-key",
        app_api_key=API_KEY,
    )
    application = create_app(service=service, settings=settings)
    return application, extractor


def request(application, method: str, path: str, **kwargs):
    async def send():
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_post_lead_requires_api_key(api_context):
    application, extractor = api_context

    response = request(application, "POST", "/leads", json={"mensagem": MESSAGE})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert API_KEY not in response.text
    assert extractor.calls == 0


def test_post_lead_returns_processed_result(api_context):
    application, extractor = api_context

    response = request(
        application,
        "POST",
        "/leads",
        headers={"X-API-Key": API_KEY},
        json={"mensagem": MESSAGE, "email": "carlos@example.com"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status_processamento"] == "PROCESSED"
    assert payload["classificacao"] == "QUENTE"
    assert payload["score"] == 100
    assert extractor.calls == 1


def test_invalid_payload_does_not_call_gemini(api_context):
    application, extractor = api_context

    response = request(
        application,
        "POST",
        "/leads",
        headers={"X-API-Key": API_KEY},
        json={"mensagem": "", "score": 100},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert extractor.calls == 0


def test_gemini_failure_is_persisted_for_review(api_context):
    application, extractor = api_context
    extractor.outcome = ExtractionOutcome(None, ReviewReason.GEMINI_TIMEOUT)

    response = request(
        application,
        "POST",
        "/leads",
        headers={"X-API-Key": API_KEY},
        json={"mensagem": "Preciso de ajuda"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status_processamento"] == "REVIEW_REQUIRED"
    assert payload["review_reason"] == "gemini_timeout"
    assert payload["score"] is None
    assert payload["classificacao"] is None


def test_oversized_http_body_is_rejected_before_gemini(api_context):
    application, extractor = api_context

    response = request(
        application,
        "POST",
        "/leads",
        headers={"X-API-Key": API_KEY},
        content=b"x" * 20_000,
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert extractor.calls == 0


def test_get_endpoints_return_data_without_calling_gemini(api_context):
    application, extractor = api_context
    created = request(
        application,
        "POST",
        "/leads",
        headers={"X-API-Key": API_KEY},
        json={"mensagem": MESSAGE, "email": "carlos@example.com"},
    )
    extractor.calls = 0
    lead_id = created.json()["id"]

    detail = request(application, "GET", f"/leads/{lead_id}", headers={"X-API-Key": API_KEY})
    listing = request(application, "GET", "/leads", headers={"X-API-Key": API_KEY})

    assert detail.status_code == 200
    assert detail.json()["email"] == "carlos@example.com"
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert "email" not in listing.json()["items"][0]
    assert "mensagem_original" not in listing.json()["items"][0]
    assert extractor.calls == 0


def test_get_missing_lead_returns_safe_not_found(api_context):
    application, _ = api_context

    response = request(
        application,
        "GET",
        "/leads/00000000-0000-0000-0000-000000000000",
        headers={"X-API-Key": API_KEY},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LEAD_NOT_FOUND"


def test_sql_injection_text_is_stored_as_data(api_context):
    application, _ = api_context
    hostile_message = "'; DROP TABLE leads; --"

    response = request(
        application,
        "POST",
        "/leads",
        headers={"X-API-Key": API_KEY},
        json={"mensagem": hostile_message},
    )

    assert response.status_code == 201
    lead_id = response.json()["id"]
    detail = request(application, "GET", f"/leads/{lead_id}", headers={"X-API-Key": API_KEY})
    assert detail.status_code == 200
    assert detail.json()["mensagem_original"] == hostile_message


def test_database_error_returns_safe_503():
    class BrokenService:
        def create(self, *args, **kwargs):
            raise SQLAlchemyError("password=redacted; connection string omitted")

    settings = Settings(
        database_url="sqlite:///:memory:",
        gemini_api_key="local-test-key",
        app_api_key=API_KEY,
    )
    application = create_app(service=BrokenService(), settings=settings)

    response = request(
        application,
        "POST",
        "/leads",
        headers={"X-API-Key": API_KEY},
        json={"mensagem": MESSAGE},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "password" not in response.text
    assert "connection string" not in response.text
