import json
import logging
from typing import Any

_SAFE_FIELDS = frozenset(
    {
        "request_id",
        "lead_id",
        "status",
        "duration_ms",
        "score",
        "classification",
        "reason",
        "model",
        "rule_version",
        "error_type",
    }
)


def configure_logging(level: str = "INFO") -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=numeric_level, format="%(message)s")


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    safe_fields = {key: value for key, value in fields.items() if key in _SAFE_FIELDS}
    logger.info(json.dumps({"event": event, **safe_fields}, default=str, sort_keys=True))
