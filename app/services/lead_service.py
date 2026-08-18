from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.integrations.gemini import ExtractionOutcome, GeminiExtraction, ReviewReason
from app.logging_config import log_event
from app.persistence.lead_repository import LeadInsert, LeadRepository
from app.persistence.models import Lead
from app.schemas.lead import (
    Classification,
    Intent,
    LeadCreateRequest,
    LeadListItem,
    LeadResponse,
    ProcessingStatus,
    Urgency,
)
from app.services.classifier import RULE_VERSION, ClassificationInput, classify_lead

logger = logging.getLogger(__name__)


class Extractor(Protocol):
    def extract(self, message: str) -> ExtractionOutcome: ...


class LeadService:
    def __init__(self, *, session_factory: Callable[[], Session], extractor: Extractor):
        self._session_factory = session_factory
        self._extractor = extractor

    def create(self, request: LeadCreateRequest, *, request_id: str | None = None) -> LeadResponse:
        log_event(logger, "lead_received", request_id=request_id)
        outcome = self._extractor.extract(request.mensagem)
        log_event(
            logger,
            "gemini_output_validated",
            request_id=request_id,
            reason=outcome.review_reason.value if outcome.review_reason else "valid",
        )

        if outcome.data is not None:
            result = classify_lead(self._classification_input(outcome.data, request))
            insert = self._processed_insert(request, outcome.data, result)
            motivos = list(result.motivos)
            log_event(
                logger,
                "lead_classified",
                request_id=request_id,
                score=result.score,
                classification=result.classificacao.value,
                rule_version=result.versao_regras,
            )
        else:
            review_reason = outcome.review_reason or ReviewReason.INVALID_LLM_OUTPUT
            insert = self._review_insert(request, review_reason)
            motivos = None
            log_event(
                logger, "lead_marked_for_review", request_id=request_id, reason=review_reason.value
            )

        with self._session_factory() as session:
            with session.begin():
                lead = LeadRepository(session).create(insert)
            response = self._to_response(lead, motivos=motivos)

        log_event(logger, "lead_persisted", request_id=request_id, lead_id=str(response.id))
        return response

    def get(self, lead_id: UUID) -> LeadResponse | None:
        with self._session_factory() as session:
            lead = LeadRepository(session).get(lead_id)
            if lead is None:
                return None
            return self._to_response(lead, motivos=self._motivos_for_lead(lead))

    def list(
        self,
        *,
        limit: int,
        offset: int,
        classificacao: Classification | None = None,
        status: ProcessingStatus | None = None,
    ) -> tuple[list[LeadListItem], int]:
        with self._session_factory() as session:
            leads, total = LeadRepository(session).list(
                limit=limit,
                offset=offset,
                classificacao=classificacao,
                status=status,
            )
            return [self._to_list_item(lead) for lead in leads], total

    @staticmethod
    def _classification_input(
        data: GeminiExtraction, request: LeadCreateRequest
    ) -> ClassificationInput:
        return ClassificationInput(
            intent=data.intencao,
            quantity=data.quantidade,
            urgency=data.urgencia,
            company_present=data.empresa is not None,
            contact_present=request.email is not None or request.telefone is not None,
        )

    @staticmethod
    def _processed_insert(request, data: GeminiExtraction, result) -> LeadInsert:
        return LeadInsert(
            nome=data.nome,
            empresa=data.empresa,
            email=str(request.email) if request.email is not None else None,
            telefone=request.telefone,
            mensagem_original=request.mensagem,
            produto_interesse=data.produto_interesse,
            quantidade=data.quantidade,
            prazo=data.prazo,
            intencao=data.intencao,
            urgencia=data.urgencia,
            score=result.score,
            classificacao=result.classificacao,
            status_processamento=ProcessingStatus.PROCESSED,
            review_reason=None,
            versao_regras=result.versao_regras,
        )

    @staticmethod
    def _review_insert(request: LeadCreateRequest, review_reason: ReviewReason) -> LeadInsert:
        return LeadInsert(
            email=str(request.email) if request.email is not None else None,
            telefone=request.telefone,
            mensagem_original=request.mensagem,
            status_processamento=ProcessingStatus.REVIEW_REQUIRED,
            review_reason=review_reason.value,
            versao_regras=RULE_VERSION,
        )

    @classmethod
    def _motivos_for_lead(cls, lead: Lead) -> list[str] | None:
        if lead.status_processamento != ProcessingStatus.PROCESSED.value:
            return None
        result = classify_lead(
            ClassificationInput(
                intent=Intent(lead.intencao) if lead.intencao else None,
                quantity=lead.quantidade,
                urgency=Urgency(lead.urgencia) if lead.urgencia else None,
                company_present=lead.empresa is not None,
                contact_present=lead.email is not None or lead.telefone is not None,
            )
        )
        return list(result.motivos)

    @classmethod
    def _to_response(cls, lead: Lead, *, motivos: list[str] | None) -> LeadResponse:
        return LeadResponse(
            id=lead.id,
            status_processamento=ProcessingStatus(lead.status_processamento),
            nome=lead.nome,
            empresa=lead.empresa,
            email=lead.email,
            telefone=lead.telefone,
            mensagem_original=lead.mensagem_original,
            produto_interesse=lead.produto_interesse,
            quantidade=lead.quantidade,
            prazo=lead.prazo,
            intencao=Intent(lead.intencao) if lead.intencao else None,
            urgencia=Urgency(lead.urgencia) if lead.urgencia else None,
            score=lead.score,
            classificacao=Classification(lead.classificacao) if lead.classificacao else None,
            review_reason=lead.review_reason,
            motivos=motivos,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )

    @staticmethod
    def _to_list_item(lead: Lead) -> LeadListItem:
        return LeadListItem(
            id=lead.id,
            status_processamento=ProcessingStatus(lead.status_processamento),
            nome=lead.nome,
            empresa=lead.empresa,
            produto_interesse=lead.produto_interesse,
            score=lead.score,
            classificacao=Classification(lead.classificacao) if lead.classificacao else None,
            created_at=lead.created_at,
        )
