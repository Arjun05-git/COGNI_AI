from __future__ import annotations

import logging
import sqlite3
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from app.charts import build_chart_payload
from app.config import settings
from app.db import check_database_connection, execute_query
from app.logging_utils import configure_logging
from app.memory_store import count_seed_records
from app.middleware import RequestLoggingMiddleware
from app.nl2sql import generate_sql_from_agent
from app.question_bank import QUESTION_SQL_FALLBACKS, match_question_to_sql, normalize_question
from app.schemas import ChatRequest, ChatResponse, HealthResponse
from app.sql_safety import SqlValidationError, validate_sql_is_safe
from vanna_setup import get_agent_components


configure_logging()
logger = logging.getLogger("clinic_nl2sql.api")

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_middleware(RequestLoggingMiddleware)
INDEX_FILE = Path(__file__).resolve().parent / "index.html"

agent_components = None


def _get_agent_components():
    global agent_components
    if agent_components is None:
        agent_components = get_agent_components()
    return agent_components


def _build_message(question: str, row_count: int) -> str:
    if row_count == 0:
        return f'No data found for "{question}".'
    if row_count == 1:
        return f'Found 1 row for "{question}".'
    return f'Found {row_count} rows for "{question}".'


def _debug_payload(
    *,
    source: str,
    stage: str,
    method_name: str | None = None,
    fallback_source: str | None = None,
    raw_preview: str | None = None,
    detail: str | None = None,
) -> dict[str, str]:
    payload = {
        "source": source,
        "stage": stage,
    }
    if method_name:
        payload["method_name"] = method_name
    if fallback_source:
        payload["fallback_source"] = fallback_source
    if raw_preview:
        payload["raw_preview"] = raw_preview
    if detail:
        payload["detail"] = detail
    return payload


@lru_cache(maxsize=128)
def _fallback_sql_for_question(question: str) -> tuple[str | None, str | None]:
    normalized = normalize_question(question)
    direct = QUESTION_SQL_FALLBACKS.get(normalized)
    if direct:
        return direct, "direct_assignment_match"
    return match_question_to_sql(question)


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="Frontend file not found.")
    return FileResponse(INDEX_FILE)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    database_ok = check_database_connection(settings.database_path)
    try:
        _get_agent_components()
        agent_ready = True
    except Exception:
        agent_ready = False

    status = "ok" if database_ok and agent_ready else "degraded"
    database = "connected" if database_ok else "error"
    return HealthResponse(
        status=status,
        database=database,
        agent_memory_items=count_seed_records(settings.memory_seed_path),
        llm_provider=settings.llm_provider,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    question = payload.question.strip()
    fallback_sql, fallback_source = _fallback_sql_for_question(question)
    try:
        generated = await generate_sql_from_agent(_get_agent_components().agent, question)
        sql_query = validate_sql_is_safe(generated.sql)
        columns, rows = execute_query(settings.database_path, sql_query)
        chart, chart_type = build_chart_payload(columns, rows)
        return ChatResponse(
            message=_build_message(question, len(rows)),
            sql_query=sql_query,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            chart=chart,
            chart_type=chart_type,
            error=None,
            debug=_debug_payload(
                source="agent",
                stage=(
                    "agent_catalog_recovered"
                    if generated.used_catalog_recovery
                    else "agent_canonicalized"
                    if generated.canonicalized
                    else "success"
                ),
                method_name=generated.method_name,
                raw_preview=generated.raw_preview,
                detail=(
                    "Recovered with canonical SQL template after a non-SQL agent response."
                    if generated.used_catalog_recovery
                    else "Canonical SQL template applied for exact assignment question."
                    if generated.canonicalized
                    else None
                ),
            ),
        )
    except SqlValidationError as exc:
        if fallback_sql:
            columns, rows = execute_query(settings.database_path, fallback_sql)
            chart, chart_type = build_chart_payload(columns, rows)
            logger.warning(
                "fallback_used_after_validation_failure",
                extra={
                    "event": "fallback_used_after_validation_failure",
                    "stage": "fallback",
                    "question": question,
                    "preview": str(exc),
                },
            )
            return ChatResponse(
                message=f'{_build_message(question, len(rows))} Fallback path used.',
                sql_query=fallback_sql,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                chart=chart,
                chart_type=chart_type,
                error=f"Primary SQL was rejected by safety validation. Recovered via {fallback_source}.",
                debug=_debug_payload(
                    source="fallback",
                    stage="sql_validation_failed",
                    fallback_source=fallback_source,
                    detail=str(exc),
                ),
            )
        logger.warning(
            "sql_validation_failed",
            extra={
                "event": "sql_validation_failed",
                "request_id": getattr(request.state, "request_id", None),
            },
        )
        raise HTTPException(
            status_code=400,
            detail=ChatResponse(
                message="The generated SQL was rejected by the safety validator.",
                sql_query=None,
                columns=[],
                rows=[],
                row_count=0,
                chart=None,
                chart_type=None,
                error=str(exc),
            ).model_dump(),
        ) from exc
    except sqlite3.Error as exc:
        if fallback_sql:
            try:
                columns, rows = execute_query(settings.database_path, fallback_sql)
                chart, chart_type = build_chart_payload(columns, rows)
                logger.warning(
                    "fallback_used_after_db_error",
                    extra={
                        "event": "fallback_used_after_db_error",
                        "stage": "fallback",
                        "question": question,
                        "preview": str(exc),
                    },
                )
                return ChatResponse(
                    message=f'{_build_message(question, len(rows))} Fallback path used.',
                    sql_query=fallback_sql,
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    chart=chart,
                    chart_type=chart_type,
                    error=f"Primary SQL failed during execution. Recovered via {fallback_source}.",
                    debug=_debug_payload(
                        source="fallback",
                        stage="db_execution_failed",
                        fallback_source=fallback_source,
                        detail=str(exc),
                    ),
                )
            except sqlite3.Error:
                pass
        logger.exception(
            "database_execution_failed",
            extra={
                "event": "database_execution_failed",
                "request_id": getattr(request.state, "request_id", None),
            },
        )
        raise HTTPException(
            status_code=500,
            detail=ChatResponse(
                message="The query could not be executed against the database.",
                sql_query=None,
                columns=[],
                rows=[],
                row_count=0,
                chart=None,
                chart_type=None,
                error=str(exc),
            ).model_dump(),
        ) from exc
    except Exception as exc:
        if fallback_sql:
            try:
                columns, rows = execute_query(settings.database_path, fallback_sql)
                chart, chart_type = build_chart_payload(columns, rows)
                logger.warning(
                    "fallback_used_after_agent_failure",
                    extra={
                        "event": "fallback_used_after_agent_failure",
                        "stage": "fallback",
                        "question": question,
                        "preview": str(exc),
                    },
                )
                return ChatResponse(
                    message=f'{_build_message(question, len(rows))} Fallback path used.',
                    sql_query=fallback_sql,
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    chart=chart,
                    chart_type=chart_type,
                    error=f"Primary agent path failed. Recovered via {fallback_source}.",
                    debug=_debug_payload(
                        source="fallback",
                        stage="agent_failed",
                        fallback_source=fallback_source,
                        detail=str(exc),
                    ),
                )
            except sqlite3.Error:
                pass
        logger.exception(
            "chat_processing_failed",
            extra={
                "event": "chat_processing_failed",
                "request_id": getattr(request.state, "request_id", None),
            },
        )
        raise HTTPException(
            status_code=500,
            detail=ChatResponse(
                message="The agent could not process the question.",
                sql_query=None,
                columns=[],
                rows=[],
                row_count=0,
                chart=None,
                chart_type=None,
                error=str(exc),
            ).model_dump(),
        ) from exc
