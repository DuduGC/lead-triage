import logging

from app.logging_config import log_event


def test_log_event_drops_pii_and_secret_fields(caplog):
    logger = logging.getLogger("lead_triage.test")

    with caplog.at_level(logging.INFO, logger="lead_triage.test"):
        log_event(
            logger,
            "lead_received",
            request_id="request-123",
            lead_id="lead-123",
            message="Carlos pediu orçamento",
            email="carlos@example.com",
            api_key="must-not-log",
        )

    output = caplog.text
    assert "lead_received" in output
    assert "request-123" in output
    assert "Carlos pediu orçamento" not in output
    assert "carlos@example.com" not in output
    assert "must-not-log" not in output
