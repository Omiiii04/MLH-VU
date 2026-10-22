from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Severity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"


class Diagnostic(BaseModel):
    code: str
    severity: Severity
    message: str
    line_start: int | None = None
    line_end: int | None = None
    suggestion: str | None = None


def d(
    code: str,
    message: str,
    *,
    severity: Severity = Severity.error,
    line_start: int | None = None,
    line_end: int | None = None,
    suggestion: str | None = None,
) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=severity,
        message=message,
        line_start=line_start,
        line_end=line_end,
        suggestion=suggestion,
    )


class CompileStatus(str, Enum):
    COMPILED = "COMPILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECTED = "REJECTED"


POSTCONDITION_KINDS = frozenset(
    {
        "file_exists",
        "file_contains_fields",
        "json_matches_schema",
        "row_count_delta",
        "checksum_equals",
        "schema_unchanged",
        "http_status",
    }
)

VACUOUS_KINDS = frozenset({"always_true", "true", "pass", "noop"})
