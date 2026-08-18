import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

MESSAGE_MAX_LENGTH = 5000
PHONE_MAX_LENGTH = 32
QUANTITY_MAX = 1_000_000

_PHONE_ALLOWED = re.compile(r"^\+?[0-9 .()\-]+$")


class Intent(StrEnum):
    SOLICITAR_ORCAMENTO = "solicitar_orcamento"
    COMPRAR = "comprar"
    PESQUISAR = "pesquisar"
    OUTRO = "outro"
    DESCONHECIDA = "desconhecida"


class Urgency(StrEnum):
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"
    DESCONHECIDA = "desconhecida"


class Classification(StrEnum):
    QUENTE = "QUENTE"
    MORNO = "MORNO"
    FRIO = "FRIO"


class ProcessingStatus(StrEnum):
    PROCESSED = "PROCESSED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


ShortText = Annotated[str, StringConstraints(min_length=1, max_length=160)]


class LeadCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    mensagem: Annotated[
        str,
        StringConstraints(min_length=1, max_length=MESSAGE_MAX_LENGTH),
    ]
    email: EmailStr | None = None
    telefone: (
        Annotated[
            str,
            StringConstraints(min_length=1, max_length=PHONE_MAX_LENGTH),
        ]
        | None
    ) = None

    @field_validator("telefone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        if not _PHONE_ALLOWED.fullmatch(value):
            raise ValueError("telefone must contain only phone characters")

        digits = re.sub(r"\D", "", value)
        if not 8 <= len(digits) <= 20:
            raise ValueError("telefone must contain between 8 and 20 digits")

        return ("+" if value.startswith("+") else "") + digits


class LeadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    status_processamento: ProcessingStatus
    nome: ShortText | None
    empresa: ShortText | None
    email: EmailStr | None
    telefone: str | None
    mensagem_original: Annotated[
        str,
        StringConstraints(min_length=1, max_length=MESSAGE_MAX_LENGTH),
    ]
    produto_interesse: ShortText | None
    quantidade: Annotated[int, Field(ge=1, le=QUANTITY_MAX)] | None
    prazo: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None
    intencao: Intent | None
    urgencia: Urgency | None
    score: Annotated[int, Field(ge=0, le=100)] | None
    classificacao: Classification | None
    review_reason: Annotated[str, StringConstraints(min_length=1, max_length=40)] | None
    motivos: list[str] | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_processing_consistency(self):
        if self.status_processamento is ProcessingStatus.PROCESSED:
            if self.score is None or self.classificacao is None or self.review_reason is not None:
                raise ValueError("processed lead must have classification and no review reason")
        elif self.score is not None or self.classificacao is not None or self.review_reason is None:
            raise ValueError("review lead must have a reason and no score or classification")
        return self


class LeadListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    status_processamento: ProcessingStatus
    nome: ShortText | None
    empresa: ShortText | None
    produto_interesse: ShortText | None
    score: Annotated[int, Field(ge=0, le=100)] | None
    classificacao: Classification | None
    created_at: datetime


class LeadListResponse(BaseModel):
    items: list[LeadListItem]
    total: Annotated[int, Field(ge=0)]
    limit: Annotated[int, Field(ge=1, le=100)]
    offset: Annotated[int, Field(ge=0)]
