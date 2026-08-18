from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.persistence.models import Lead
from app.schemas.lead import Classification, Intent, ProcessingStatus, Urgency


@dataclass(frozen=True, slots=True)
class LeadInsert:
    mensagem_original: str
    status_processamento: ProcessingStatus
    versao_regras: str
    nome: str | None = None
    empresa: str | None = None
    email: str | None = None
    telefone: str | None = None
    produto_interesse: str | None = None
    quantidade: int | None = None
    prazo: str | None = None
    intencao: Intent | None = None
    urgencia: Urgency | None = None
    score: int | None = None
    classificacao: Classification | None = None
    review_reason: str | None = None
    id: UUID = field(default_factory=uuid4)


def _value(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


class LeadRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, data: LeadInsert) -> Lead:
        lead = Lead(
            id=data.id,
            nome=data.nome,
            empresa=data.empresa,
            email=data.email,
            telefone=data.telefone,
            mensagem_original=data.mensagem_original,
            produto_interesse=data.produto_interesse,
            quantidade=data.quantidade,
            prazo=data.prazo,
            intencao=_value(data.intencao),
            urgencia=_value(data.urgencia),
            score=data.score,
            classificacao=_value(data.classificacao),
            status_processamento=_value(data.status_processamento),
            review_reason=data.review_reason,
            versao_regras=data.versao_regras,
        )
        self.session.add(lead)
        self.session.flush()
        return lead

    def get(self, lead_id: UUID) -> Lead | None:
        return self.session.get(Lead, lead_id)

    def list(
        self,
        *,
        limit: int,
        offset: int,
        classificacao: Classification | None = None,
        status: ProcessingStatus | None = None,
    ) -> tuple[list[Lead], int]:
        filters = []
        if classificacao is not None:
            filters.append(Lead.classificacao == _value(classificacao))
        if status is not None:
            filters.append(Lead.status_processamento == _value(status))

        total = self.session.scalar(select(func.count()).select_from(Lead).where(*filters)) or 0
        items = list(
            self.session.scalars(
                select(Lead)
                .where(*filters)
                .order_by(Lead.created_at.desc(), Lead.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total
