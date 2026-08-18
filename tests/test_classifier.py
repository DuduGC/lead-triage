import pytest
from pydantic import ValidationError

from app.schemas.lead import Classification, Intent, Urgency
from app.services.classifier import ClassificationInput, classify_lead


def lead(**overrides) -> ClassificationInput:
    values = {
        "intent": None,
        "quantity": None,
        "urgency": None,
        "company_present": False,
        "contact_present": False,
    }
    values.update(overrides)
    return ClassificationInput(**values)


def test_reference_lead_is_hot_with_a_deterministic_score():
    result = classify_lead(
        lead(
            intent=Intent.SOLICITAR_ORCAMENTO,
            quantity=15,
            urgency=Urgency.ALTA,
            company_present=True,
        )
    )

    assert result.score == 90
    assert result.classificacao is Classification.QUENTE
    assert result.motivos == (
        "intent_high",
        "quantity_10_plus",
        "urgency_high",
        "company_present",
    )
    assert result.versao_regras == "v1"


@pytest.mark.parametrize(
    ("input_data", "expected_score", "expected_classification"),
    [
        (lead(intent=Intent.SOLICITAR_ORCAMENTO), 35, Classification.FRIO),
        (
            lead(intent=Intent.SOLICITAR_ORCAMENTO, quantity=1),
            40,
            Classification.MORNO,
        ),
        (
            lead(
                intent=Intent.SOLICITAR_ORCAMENTO,
                quantity=2,
                urgency=Urgency.MEDIA,
                company_present=True,
            ),
            70,
            Classification.QUENTE,
        ),
    ],
)
def test_classification_thresholds_are_inclusive(
    input_data, expected_score, expected_classification
):
    result = classify_lead(input_data)

    assert result.score == expected_score
    assert result.classificacao is expected_classification


@pytest.mark.parametrize(
    ("quantity", "expected_points"),
    [(None, 0), (1, 5), (2, 15), (9, 15), (10, 25)],
)
def test_quantity_points_cover_each_boundary(quantity, expected_points):
    result = classify_lead(lead(quantity=quantity))

    assert result.score == expected_points


@pytest.mark.parametrize(
    ("urgency", "expected_points"),
    [
        (None, 0),
        (Urgency.DESCONHECIDA, 0),
        (Urgency.BAIXA, 5),
        (Urgency.MEDIA, 15),
        (Urgency.ALTA, 25),
    ],
)
def test_urgency_points_are_deterministic(urgency, expected_points):
    result = classify_lead(lead(urgency=urgency))

    assert result.score == expected_points


def test_buying_intent_and_contact_receive_expected_points():
    result = classify_lead(
        lead(
            intent=Intent.COMPRAR,
            company_present=True,
            contact_present=True,
        )
    )

    assert result.score == 50
    assert result.classificacao is Classification.MORNO
    assert result.motivos == ("intent_high", "company_present", "contact_present")


def test_unknown_information_does_not_receive_points():
    result = classify_lead(lead(intent=Intent.DESCONHECIDA, urgency=Urgency.DESCONHECIDA))

    assert result.score == 0
    assert result.classificacao is Classification.FRIO
    assert result.motivos == ()


def test_all_positive_signals_are_capped_at_one_hundred():
    result = classify_lead(
        lead(
            intent=Intent.COMPRAR,
            quantity=10,
            urgency=Urgency.ALTA,
            company_present=True,
            contact_present=True,
        )
    )

    assert result.score == 100
    assert result.classificacao is Classification.QUENTE


@pytest.mark.parametrize("quantity", [0, -1, 1_000_001])
def test_invalid_quantity_is_rejected_before_classification(quantity):
    with pytest.raises(ValidationError):
        lead(quantity=quantity)


def test_classification_input_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ClassificationInput(quantity=1, score=100)
