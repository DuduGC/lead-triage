"""create leads table

Revision ID: 0001_create_leads
Revises:
Create Date: 2026-08-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_create_leads"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=True),
        sa.Column("empresa", sa.String(length=160), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("telefone", sa.String(length=32), nullable=True),
        sa.Column("mensagem_original", sa.Text(), nullable=False),
        sa.Column("produto_interesse", sa.String(length=160), nullable=True),
        sa.Column("quantidade", sa.Integer(), nullable=True),
        sa.Column("prazo", sa.String(length=120), nullable=True),
        sa.Column("intencao", sa.String(length=32), nullable=True),
        sa.Column("urgencia", sa.String(length=16), nullable=True),
        sa.Column("score", sa.SmallInteger(), nullable=True),
        sa.Column("classificacao", sa.String(length=16), nullable=True),
        sa.Column("status_processamento", sa.String(length=24), nullable=False),
        sa.Column("review_reason", sa.String(length=40), nullable=True),
        sa.Column("versao_regras", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(mensagem_original) BETWEEN 1 AND 5000",
            name="ck_leads_message_length",
        ),
        sa.CheckConstraint(
            "quantidade IS NULL OR quantidade BETWEEN 1 AND 1000000",
            name="ck_leads_quantity_range",
        ),
        sa.CheckConstraint(
            "intencao IS NULL OR intencao IN "
            "('solicitar_orcamento', 'comprar', 'pesquisar', 'outro', 'desconhecida')",
            name="ck_leads_intent_values",
        ),
        sa.CheckConstraint(
            "urgencia IS NULL OR urgencia IN ('alta', 'media', 'baixa', 'desconhecida')",
            name="ck_leads_urgency_values",
        ),
        sa.CheckConstraint(
            "classificacao IS NULL OR classificacao IN ('QUENTE', 'MORNO', 'FRIO')",
            name="ck_leads_classification_values",
        ),
        sa.CheckConstraint(
            "status_processamento IN ('PROCESSED', 'REVIEW_REQUIRED')",
            name="ck_leads_processing_status_values",
        ),
        sa.CheckConstraint(
            "score IS NULL OR score BETWEEN 0 AND 100",
            name="ck_leads_score_range",
        ),
        sa.CheckConstraint(
            "(status_processamento = 'PROCESSED' AND score IS NOT NULL "
            "AND classificacao IS NOT NULL AND review_reason IS NULL) OR "
            "(status_processamento = 'REVIEW_REQUIRED' AND score IS NULL "
            "AND classificacao IS NULL AND review_reason IS NOT NULL)",
            name="ck_leads_processing_consistency",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_created_at", "leads", ["created_at"], unique=False)
    op.create_index(
        "ix_leads_classification_created_at",
        "leads",
        ["classificacao", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_leads_status_created_at",
        "leads",
        ["status_processamento", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_leads_status_created_at", table_name="leads")
    op.drop_index("ix_leads_classification_created_at", table_name="leads")
    op.drop_index("ix_leads_created_at", table_name="leads")
    op.drop_table("leads")
