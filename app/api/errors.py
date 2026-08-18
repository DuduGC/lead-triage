from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApiError(Exception):
    status_code: int
    code: str
    message: str
