import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint(
            "length(mensagem_original) BETWEEN 1 AND 5000",
            name="ck_leads_message_length",
        ),
        CheckConstraint(
            "quantidade IS NULL OR quantidade BETWEEN 1 AND 1000000",
            name="ck_leads_quantity_range",
        ),
        CheckConstraint(
            "intencao IS NULL OR intencao IN "
            "('solicitar_orcamento', 'comprar', 'pesquisar', 'outro', 'desconhecida')",
            name="ck_leads_intent_values",
        ),
        CheckConstraint(
            "urgencia IS NULL OR urgencia IN ('alta', 'media', 'baixa', 'desconhecida')",
            name="ck_leads_urgency_values",
        ),
        CheckConstraint(
            "classificacao IS NULL OR classificacao IN ('QUENTE', 'MORNO', 'FRIO')",
            name="ck_leads_classification_values",
        ),
        CheckConstraint(
            "status_processamento IN ('PROCESSED', 'REVIEW_REQUIRED')",
            name="ck_leads_processing_status_values",
        ),
        CheckConstraint(
            "score IS NULL OR score BETWEEN 0 AND 100",
            name="ck_leads_score_range",
        ),
        CheckConstraint(
            "(status_processamento = 'PROCESSED' AND score IS NOT NULL "
            "AND classificacao IS NOT NULL AND review_reason IS NULL) OR "
            "(status_processamento = 'REVIEW_REQUIRED' AND score IS NULL "
            "AND classificacao IS NULL AND review_reason IS NOT NULL)",
            name="ck_leads_processing_consistency",
        ),
        Index("ix_leads_created_at", "created_at"),
        Index("ix_leads_classification_created_at", "classificacao", "created_at"),
        Index("ix_leads_status_created_at", "status_processamento", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str | None] = mapped_column(String(120), nullable=True)
    empresa: Mapped[str | None] = mapped_column(String(160), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mensagem_original: Mapped[str] = mapped_column(Text, nullable=False)
    produto_interesse: Mapped[str | None] = mapped_column(String(160), nullable=True)
    quantidade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prazo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    intencao: Mapped[str | None] = mapped_column(String(32), nullable=True)
    urgencia: Mapped[str | None] = mapped_column(String(16), nullable=True)
    score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    classificacao: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status_processamento: Mapped[str] = mapped_column(String(24), nullable=False)
    review_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    versao_regras: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
