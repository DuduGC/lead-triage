import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.integrations.gemini import ExtractionOutcome, GeminiExtraction, ReviewReason
from app.persistence.models import Base
from app.schemas.lead import LeadCreateRequest
from app.services.lead_service import LeadService

MESSAGE = "Olá, sou Carlos da Loja ABC. Precisamos comprar 15 computadores ainda este mês."


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
        self.messages = []

    def extract(self, message: str):
        self.messages.append(message)
        return self.outcome


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def test_service_persists_processed_lead_and_returns_python_score(session_factory):
    extractor = FakeExtractor(ExtractionOutcome(extraction_payload(), None))
    service = LeadService(session_factory=session_factory, extractor=extractor)

    response = service.create(LeadCreateRequest(mensagem=MESSAGE, email="carlos@example.com"))

    assert response.status_processamento == "PROCESSED"
    assert response.score == 100
    assert response.classificacao == "QUENTE"
    assert response.motivos == [
        "intent_high",
        "quantity_10_plus",
        "urgency_high",
        "company_present",
        "contact_present",
    ]
    assert extractor.messages == [MESSAGE]


def test_service_persists_unavailable_analysis_for_review(session_factory):
    extractor = FakeExtractor(ExtractionOutcome(None, ReviewReason.GEMINI_TIMEOUT))
    service = LeadService(session_factory=session_factory, extractor=extractor)

    response = service.create(LeadCreateRequest(mensagem="Preciso de ajuda"))

    assert response.status_processamento == "REVIEW_REQUIRED"
    assert response.score is None
    assert response.classificacao is None
    assert response.review_reason == "gemini_timeout"


def test_service_can_read_and_list_without_calling_extractor(session_factory):
    extractor = FakeExtractor(ExtractionOutcome(extraction_payload(), None))
    service = LeadService(session_factory=session_factory, extractor=extractor)
    created = service.create(LeadCreateRequest(mensagem=MESSAGE))
    extractor.messages.clear()

    found = service.get(created.id)
    items, total = service.list(limit=20, offset=0)

    assert found is not None
    assert total == 1
    assert len(items) == 1
    assert extractor.messages == []
