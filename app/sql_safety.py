from __future__ import annotations

import re


DANGEROUS_PATTERNS = (
    r"\binsert\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bdrop\b",
    r"\balter\b",
    r"\bexec(?:ute)?\b",
    r"\battach\b",
    r"\bdetach\b",
    r"\bpragma\b",
    r"\bcreate\b",
    r"\breplace\b",
    r"\btruncate\b",
    r"\bgrant\b",
    r"\brevoke\b",
    r"\bshutdown\b",
    r"\bxp_\w+\b",
    r"\bsp_\w+\b",
    r"\bsqlite_master\b",
    r"\bsqlite_schema\b",
    r"\bsqlite_temp_master\b",
)


class SqlValidationError(ValueError):
    """Raised when generated SQL does not meet safety requirements."""


def normalize_sql(sql: str) -> str:
    cleaned = sql.strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.rstrip(";").strip()


def validate_sql_is_safe(sql: str) -> str:
    normalized = normalize_sql(sql)
    lowered = normalized.lower()

    if not normalized:
        raise SqlValidationError("Generated SQL was empty.")
    if ";" in normalized:
        raise SqlValidationError("Only a single SQL statement is allowed.")
    if not (lowered.startswith("select ") or lowered.startswith("with ")):
        raise SqlValidationError("Only SELECT queries are allowed.")

    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, lowered):
            raise SqlValidationError("Generated SQL contains a blocked keyword or system table.")

    if lowered.startswith("with ") and " select " not in f" {lowered} ":
        raise SqlValidationError("CTE queries must resolve to a SELECT statement.")

    return normalized
