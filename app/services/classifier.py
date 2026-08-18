from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.schemas.lead import Classification, Intent, Urgency

RULE_VERSION = "v1"
QUANTITY_MAX = 1_000_000


class ClassificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Intent | None = None
    quantity: Annotated[int, Field(strict=True, ge=1, le=QUANTITY_MAX)] | None = None
    urgency: Urgency | None = None
    company_present: StrictBool = False
    contact_present: StrictBool = False


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    score: int
    classificacao: Classification
    motivos: tuple[str, ...]
    versao_regras: str = RULE_VERSION


def classify_lead(data: ClassificationInput) -> ClassificationResult:
    score = 0
    reasons: list[str] = []

    if data.intent in (Intent.SOLICITAR_ORCAMENTO, Intent.COMPRAR):
        score += 35
        reasons.append("intent_high")
    elif data.intent is Intent.PESQUISAR:
        score += 10
        reasons.append("intent_research")

    if data.quantity is not None:
        if data.quantity >= 10:
            score += 25
            reasons.append("quantity_10_plus")
        elif data.quantity >= 2:
            score += 15
            reasons.append("quantity_2_to_9")
        else:
            score += 5
            reasons.append("quantity_one")

    urgency_points = {
        Urgency.ALTA: (25, "urgency_high"),
        Urgency.MEDIA: (15, "urgency_medium"),
        Urgency.BAIXA: (5, "urgency_low"),
    }
    if data.urgency in urgency_points:
        points, reason = urgency_points[data.urgency]
        score += points
        reasons.append(reason)

    if data.company_present:
        score += 5
        reasons.append("company_present")

    if data.contact_present:
        score += 10
        reasons.append("contact_present")

    if score >= 70:
        classification = Classification.QUENTE
    elif score >= 40:
        classification = Classification.MORNO
    else:
        classification = Classification.FRIO

    return ClassificationResult(
        score=score,
        classificacao=classification,
        motivos=tuple(reasons),
    )
