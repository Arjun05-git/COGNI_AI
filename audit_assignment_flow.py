from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

import main
from app.config import settings
from app.db import execute_query, get_connection
from app.question_bank import QUESTION_SQL_FALLBACKS, normalize_question
from app.sql_safety import normalize_sql, validate_sql_is_safe


QUESTIONS = [
    "How many patients do we have?",
    "List all doctors and their specializations",
    "Show me appointments for last month",
    "Which doctor has the most appointments?",
    "What is the total revenue?",
    "Show revenue by doctor",
    "How many cancelled appointments last quarter?",
    "Top 5 patients by spending",
    "Average treatment cost by specialization",
    "Show monthly appointment count for the past 6 months",
    "Which city has the most patients?",
    "List patients who visited more than 3 times",
    "Show unpaid invoices",
    "What percentage of appointments are no-shows?",
    "Show the busiest day of the week for appointments",
    "Revenue trend by month",
    "Average appointment duration by doctor",
    "List patients with overdue invoices",
    "Compare revenue between departments",
    "Show patient registration trend by month",
]


def _schema_snapshot() -> dict[str, list[str]]:
    snapshot: dict[str, list[str]] = {}
    with get_connection(settings.database_path) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for row in tables:
            table_name = row[0]
            columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            snapshot[table_name] = [column[1] for column in columns]
    return snapshot


def main_audit() -> None:
    client = TestClient(main.app)
    schema = _schema_snapshot()
    passed = 0
    lines = [
        "# Assignment Audit Report",
        "",
        f"- Executed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- LLM Provider: {settings.llm_provider}",
        f"- Database path: {settings.database_path}",
        "",
        "## Schema Snapshot",
        "",
    ]

    for table_name, columns in schema.items():
        lines.append(f"- `{table_name}`: {', '.join(columns)}")

    lines.extend(
        [
            "",
            "## End-to-End Audit",
            "",
            "| # | Question | Canonical SQL Safe | Canonical SQL Executes | `/chat` Status | Source | SQL Match | Returned Columns | Row Count Match | Audit |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )

    for index, question in enumerate(QUESTIONS, start=1):
        canonical_sql = QUESTION_SQL_FALLBACKS[normalize_question(question)]
        safe_sql = validate_sql_is_safe(canonical_sql)
        expected_columns, expected_rows = execute_query(settings.database_path, safe_sql)

        response = client.post("/chat", json={"question": question})
        body = response.json()
        debug = body.get("debug", {}) if isinstance(body, dict) else {}
        source = debug.get("source", "unknown") if isinstance(debug, dict) else "unknown"
        returned_sql = body.get("sql_query", "") if isinstance(body, dict) else ""
        returned_columns = body.get("columns", []) if isinstance(body, dict) else []
        row_count = body.get("row_count", 0) if isinstance(body, dict) else 0

        sql_match = normalize_sql(returned_sql) == normalize_sql(canonical_sql)
        columns_match = returned_columns == expected_columns
        row_count_match = row_count == len(expected_rows)
        audit_ok = all(
            [
                response.status_code == 200,
                sql_match,
                columns_match,
                row_count_match,
            ]
        )
        if audit_ok:
            passed += 1

        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    question.replace("|", "\\|"),
                    "Y",
                    "Y",
                    str(response.status_code),
                    str(source).replace("|", "\\|"),
                    "Y" if sql_match else "N",
                    ", ".join(map(str, returned_columns)).replace("|", "\\|"),
                    "Y" if row_count_match else "N",
                    "PASS" if audit_ok else "FAIL",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Passed: {passed}/{len(QUESTIONS)}",
            "- This audit checks the canonical assignment SQL, verifies it executes, then verifies `/chat` returns the expected SQL shape, columns, and row counts.",
        ]
    )

    with open("AUDIT.md", "w", encoding="utf-8") as file_handle:
        file_handle.write("\n".join(lines))

    print(f"Completed audit. Passed {passed}/{len(QUESTIONS)} and updated AUDIT.md")


if __name__ == "__main__":
    main_audit()
