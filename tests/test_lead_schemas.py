from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.lead import (
    Classification,
    LeadCreateRequest,
    LeadResponse,
    ProcessingStatus,
)


def test_lead_request_strips_message_and_normalizes_phone():
    request = LeadCreateRequest(
        mensagem="  Olá, sou Carlos da Loja ABC.  ",
        email="carlos@example.com",
        telefone="+55 (11) 99999-8888",
    )

    assert request.mensagem == "Olá, sou Carlos da Loja ABC."
    assert request.email is not None
    assert str(request.email) == "carlos@example.com"
    assert request.telefone == "+5511999998888"


def test_lead_request_rejects_blank_message():
    with pytest.raises(ValidationError):
        LeadCreateRequest(mensagem="   ")


def test_lead_request_rejects_message_over_limit():
    with pytest.raises(ValidationError):
        LeadCreateRequest(mensagem="a" * 5001)


def test_lead_request_rejects_invalid_email_and_phone():
    with pytest.raises(ValidationError):
        LeadCreateRequest(mensagem="Olá", email="not-an-email")

    with pytest.raises(ValidationError):
        LeadCreateRequest(mensagem="Olá", telefone="+55 ABC")


def test_lead_request_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        LeadCreateRequest(mensagem="Olá", score=100)


def test_lead_response_accepts_processed_lead():
    response = LeadResponse(
        id=uuid4(),
        status_processamento=ProcessingStatus.PROCESSED,
        nome="Carlos",
        empresa="Loja ABC",
        email="carlos@example.com",
        telefone=None,
        mensagem_original="Olá",
        produto_interesse="computadores",
        quantidade=15,
        prazo="este mês",
        intencao="solicitar_orcamento",
        urgencia="alta",
        score=90,
        classificacao=Classification.QUENTE,
        review_reason=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    assert response.classificacao is Classification.QUENTE
    assert response.score == 90


def test_lead_response_rejects_processed_lead_without_classification():
    with pytest.raises(ValidationError):
        LeadResponse(
            id=uuid4(),
            status_processamento=ProcessingStatus.PROCESSED,
            nome=None,
            empresa=None,
            email=None,
            telefone=None,
            mensagem_original="Olá",
            produto_interesse=None,
            quantidade=None,
            prazo=None,
            intencao=None,
            urgencia=None,
            score=None,
            classificacao=None,
            review_reason=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )


def test_lead_response_rejects_review_lead_with_score():
    with pytest.raises(ValidationError):
        LeadResponse(
            id=uuid4(),
            status_processamento=ProcessingStatus.REVIEW_REQUIRED,
            nome=None,
            empresa=None,
            email=None,
            telefone=None,
            mensagem_original="Olá",
            produto_interesse=None,
            quantidade=None,
            prazo=None,
            intencao=None,
            urgencia=None,
            score=10,
            classificacao=None,
            review_reason="invalid_llm_output",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )


def test_lead_response_rejects_review_lead_without_reason():
    with pytest.raises(ValidationError):
        LeadResponse(
            id=uuid4(),
            status_processamento=ProcessingStatus.REVIEW_REQUIRED,
            nome=None,
            empresa=None,
            email=None,
            telefone=None,
            mensagem_original="Olá",
            produto_interesse=None,
            quantidade=None,
            prazo=None,
            intencao=None,
            urgencia=None,
            score=None,
            classificacao=None,
            review_reason=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
