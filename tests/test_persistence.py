from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.persistence.lead_repository import LeadInsert, LeadRepository
from app.persistence.models import Base, Lead
from app.schemas.lead import Classification, Intent, ProcessingStatus, Urgency


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as current_session:
        yield current_session


def valid_lead(**overrides) -> LeadInsert:
    values = {
        "mensagem_original": "Precisamos de 15 computadores ainda este mês.",
        "nome": "Carlos",
        "empresa": "Loja ABC",
        "email": "carlos@example.com",
        "telefone": "+5511999998888",
        "produto_interesse": "computadores",
        "quantidade": 15,
        "prazo": "este mês",
        "intencao": Intent.SOLICITAR_ORCAMENTO,
        "urgencia": Urgency.ALTA,
        "score": 90,
        "classificacao": Classification.QUENTE,
        "status_processamento": ProcessingStatus.PROCESSED,
        "review_reason": None,
        "versao_regras": "v1",
    }
    values.update(overrides)
    return LeadInsert(**values)


def test_repository_creates_and_reads_lead_without_committing_itself(session):
    repository = LeadRepository(session)
    lead_id = None

    with session.begin():
        created = repository.create(valid_lead())
        lead_id = created.id
        assert created.id is not None
        assert created.created_at is not None

    stored = repository.get(lead_id)

    assert stored is not None
    assert stored.empresa == "Loja ABC"
    assert stored.classificacao == Classification.QUENTE.value


def test_repository_lists_with_pagination_and_filters(session):
    repository = LeadRepository(session)
    with session.begin():
        repository.create(valid_lead())
        repository.create(
            valid_lead(
                mensagem_original="Só estou pesquisando.",
                nome=None,
                empresa=None,
                email=None,
                telefone=None,
                produto_interesse=None,
                quantidade=None,
                prazo=None,
                intencao=Intent.PESQUISAR,
                urgencia=Urgency.DESCONHECIDA,
                score=0,
                classificacao=Classification.FRIO,
            )
        )
        repository.create(
            valid_lead(
                mensagem_original="Não foi possível interpretar.",
                nome=None,
                empresa=None,
                email=None,
                telefone=None,
                produto_interesse=None,
                quantidade=None,
                prazo=None,
                intencao=None,
                urgencia=None,
                score=None,
                classificacao=None,
                status_processamento=ProcessingStatus.REVIEW_REQUIRED,
                review_reason="invalid_llm_output",
            )
        )

    items, total = repository.list(
        limit=1,
        offset=0,
        classificacao=Classification.QUENTE,
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].classificacao == Classification.QUENTE.value


def test_repository_preserves_sql_injection_text_as_data(session):
    repository = LeadRepository(session)
    hostile_message = "'; DROP TABLE leads; --"

    with session.begin():
        created = repository.create(valid_lead(mensagem_original=hostile_message))

    stored = repository.get(created.id)
    table_count = session.scalar(select(func.count()).select_from(Lead))

    assert stored is not None
    assert stored.mensagem_original == hostile_message
    assert table_count == 1


def test_database_constraints_reject_inconsistent_processed_lead(session):
    repository = LeadRepository(session)

    with pytest.raises(IntegrityError), session.begin():
        repository.create(valid_lead(score=None, classificacao=None))


def test_database_constraints_reject_invalid_quantity(session):
    repository = LeadRepository(session)

    with pytest.raises(IntegrityError), session.begin():
        repository.create(valid_lead(quantidade=0))


def test_lead_timestamps_are_timezone_aware_when_supplied():
    timestamp = datetime.now(UTC)
    lead = Lead(
        id=uuid4(),
        mensagem_original="Mensagem válida",
        status_processamento=ProcessingStatus.REVIEW_REQUIRED.value,
        review_reason="timeout",
        versao_regras="v1",
        created_at=timestamp,
        updated_at=timestamp,
    )

    assert lead.created_at.tzinfo is not None
