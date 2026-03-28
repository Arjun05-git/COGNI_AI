from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.memory_store import load_seed_records
from app.semantic_catalog import get_catalog_prompt_context, match_question_to_catalog_entry

logger = logging.getLogger("clinic_nl2sql.agent")


@dataclass
class GeneratedSqlResult:
    sql: str
    raw_response: Any
    method_name: str
    raw_preview: str | None = None
    canonicalized: bool = False
    used_catalog_recovery: bool = False


def _extract_sql_block(text: str) -> str | None:
    fenced_match = re.search(r"```sql\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if fenced_match:
        return fenced_match.group(1).strip()

    select_match = re.search(r"((?:with|select)\s.+)", text, re.IGNORECASE | re.DOTALL)
    if select_match:
        return select_match.group(1).strip()
    return None


def summarize_agent_response(raw_response: Any, max_length: int = 600) -> str:
    try:
        if raw_response is None:
            text = "None"
        elif isinstance(raw_response, str):
            text = raw_response
        elif isinstance(raw_response, (list, dict)):
            text = json.dumps(raw_response, default=str)
        else:
            model_dump = getattr(raw_response, "model_dump", None)
            if callable(model_dump):
                text = json.dumps(model_dump(), default=str)
            else:
                text = repr(raw_response)
    except Exception as exc:
        text = f"<unserializable response: {exc}>"

    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) > max_length:
        return f"{compact[:max_length]}...<truncated>"
    return compact


def to_serializable_response(raw_response: Any, max_depth: int = 5) -> Any:
    if max_depth <= 0:
        return "<max-depth-reached>"

    if raw_response is None or isinstance(raw_response, (str, int, float, bool)):
        return raw_response

    if isinstance(raw_response, dict):
        return {
            str(key): to_serializable_response(value, max_depth=max_depth - 1)
            for key, value in raw_response.items()
        }

    if isinstance(raw_response, (list, tuple)):
        return [to_serializable_response(item, max_depth=max_depth - 1) for item in raw_response]

    model_dump = getattr(raw_response, "model_dump", None)
    if callable(model_dump):
        try:
            return to_serializable_response(model_dump(), max_depth=max_depth - 1)
        except Exception:
            pass

    if hasattr(raw_response, "__dict__"):
        try:
            return {
                key: to_serializable_response(value, max_depth=max_depth - 1)
                for key, value in vars(raw_response).items()
                if not key.startswith("_")
            }
        except Exception:
            pass

    rich_component = getattr(raw_response, "rich_component", None)
    simple_component = getattr(raw_response, "simple_component", None)
    if rich_component is not None or simple_component is not None:
        return {
            "rich_component": to_serializable_response(rich_component, max_depth=max_depth - 1),
            "simple_component": to_serializable_response(simple_component, max_depth=max_depth - 1),
        }

    return repr(raw_response)


def _serialize_seed_examples() -> str:
    records = load_seed_records(settings.memory_seed_path)
    compact_records = [{"question": item["question"], "sql": item["sql"]} for item in records[:15]]
    return json.dumps(compact_records, indent=2)


def build_prompt(question: str) -> str:
    examples_json = _serialize_seed_examples()
    semantic_catalog_json = get_catalog_prompt_context()
    return f"""
You are generating SQLite SQL for a clinic management database.
Return only SQL, wrapped in a ```sql fenced block.

Schema overview:
- patients(id, first_name, last_name, email, phone, date_of_birth, gender, city, registered_date)
- doctors(id, name, specialization, department, phone)
- appointments(id, patient_id, doctor_id, appointment_date, status, notes)
- treatments(id, appointment_id, treatment_name, cost, duration_minutes)
- invoices(id, patient_id, invoice_date, total_amount, paid_amount, status)

Rules:
- Use only SQLite-compatible SQL.
- Use only SELECT statements or CTEs that end in SELECT.
- Never query sqlite_master or system tables.
- Prefer explicit joins and readable aliases.
- "Average appointment duration by doctor" should use treatment durations joined through appointments.
- For exact assignment questions that match the semantic catalog, match the catalog SQL shape exactly:
  - keep the same selected columns
  - keep the same aliases
  - do not add extra columns
  - do not rename output fields
  - if a KPI asks for percentage, return percentage values, not ratios

Semantic KPI and report catalog:
{semantic_catalog_json}

Seed examples:
{examples_json}

Question:
{question}
""".strip()


async def _invoke_agent_method(method: Any, prompt: str) -> Any:
    try:
        from vanna_setup import build_request_context

        request_context = build_request_context()
    except Exception:
        request_context = None

    payload_attempts = [
        ((prompt,), {}),
        ((), {"message": prompt}),
        ((), {"prompt": prompt}),
        ((), {"question": prompt}),
    ]

    if request_context is not None:
        payload_attempts.extend(
            [
                ((prompt,), {"request_context": request_context}),
                ((), {"message": prompt, "request_context": request_context}),
                ((), {"prompt": prompt, "request_context": request_context}),
                ((), {"question": prompt, "request_context": request_context}),
            ]
        )

    last_error: Exception | None = None
    for args, kwargs in payload_attempts:
        try:
            logger.info(
                "agent_method_attempt",
                extra={
                    "event": "agent_method_attempt",
                    "method_name": getattr(method, "__name__", method.__class__.__name__),
                    "stage": "invoke",
                },
            )
            raw_response = method(*args, **kwargs)
            if hasattr(raw_response, "__aiter__"):
                collected = []
                async for event in raw_response:
                    collected.append(event)
                return collected
            if hasattr(raw_response, "__iter__") and not isinstance(raw_response, (str, dict, list, tuple)):
                return list(raw_response)
            if hasattr(raw_response, "__await__"):
                return await raw_response
            return raw_response
        except TypeError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    raise RuntimeError("Unable to invoke the configured Vanna agent method.")


async def generate_sql_from_agent(agent: Any, question: str) -> GeneratedSqlResult:
    prompt = build_prompt(question)
    logger.info(
        "agent_generation_started",
        extra={
            "event": "agent_generation_started",
            "stage": "agent_start",
            "question": question,
        },
    )

    for method_name in ("send_message", "chat", "run"):
        method = getattr(agent, method_name, None)
        if method is None:
            continue
        raw_response = await _invoke_agent_method(method, prompt)
        raw_payload = to_serializable_response(raw_response)
        raw_preview = summarize_agent_response(raw_payload)
        logger.info(
            "agent_response_received",
            extra={
                "event": "agent_response_received",
                "stage": "agent_response",
                "method_name": method_name,
                "preview": raw_preview,
            },
        )
        logger.info(
            "agent_response_json",
            extra={
                "event": "agent_response_json",
                "stage": "agent_response_json",
                "method_name": method_name,
                "preview": json.dumps(raw_payload, default=str)[:4000],
            },
        )
        sql = extract_sql_from_agent_response(raw_response)
        if sql:
            canonical_sql, canonicalized = _canonicalize_known_question_sql(question, sql)
            logger.info(
                "agent_sql_extracted",
                extra={
                    "event": "agent_sql_extracted",
                    "stage": "agent_parse_success",
                    "method_name": method_name,
                    "preview": canonical_sql[:300],
                },
            )
            return GeneratedSqlResult(
                sql=canonical_sql,
                raw_response=raw_response,
                method_name=method_name,
                raw_preview=raw_preview,
                canonicalized=canonicalized,
            )

        recovered_sql = _recover_known_question_sql(question)
        if recovered_sql is not None:
            logger.warning(
                "agent_sql_recovered_from_catalog",
                extra={
                    "event": "agent_sql_recovered_from_catalog",
                    "stage": "agent_catalog_recovery",
                    "method_name": method_name,
                    "question": question,
                    "preview": recovered_sql[:300],
                },
            )
            return GeneratedSqlResult(
                sql=recovered_sql,
                raw_response=raw_response,
                method_name=method_name,
                raw_preview=raw_preview,
                canonicalized=True,
                used_catalog_recovery=True,
            )

        logger.warning(
            "agent_response_unparseable",
            extra={
                "event": "agent_response_unparseable",
                "stage": "agent_parse_failed",
                "method_name": method_name,
                "preview": raw_preview,
            },
        )

    raise RuntimeError("The agent responded, but SQL could not be extracted from the response.")


def extract_sql_from_agent_response(raw_response: Any) -> str | None:
    if raw_response is None:
        return None

    if isinstance(raw_response, str):
        return _extract_sql_block(raw_response)

    if isinstance(raw_response, dict):
        for key in ("sql", "sql_query", "content", "message", "text"):
            value = raw_response.get(key)
            if isinstance(value, str):
                sql = _extract_sql_block(value)
                if sql:
                    return sql

        # Vanna 2.0 responses often nest useful text under rich/simple components.
        for key in ("rich_component", "simple_component", "data", "task", "metadata"):
            if key in raw_response:
                sql = extract_sql_from_agent_response(raw_response[key])
                if sql:
                    return sql

        events = raw_response.get("events") or raw_response.get("messages") or raw_response.get("children") or []
        for event in events:
            sql = extract_sql_from_agent_response(event)
            if sql:
                return sql

        for value in raw_response.values():
            sql = extract_sql_from_agent_response(value)
            if sql:
                return sql

    if isinstance(raw_response, list):
        for item in raw_response:
            sql = extract_sql_from_agent_response(item)
            if sql:
                return sql

    content = getattr(raw_response, "content", None)
    if isinstance(content, str):
        return _extract_sql_block(content)

    text = getattr(raw_response, "text", None)
    if isinstance(text, str):
        return _extract_sql_block(text)

    model_dump = getattr(raw_response, "model_dump", None)
    if callable(model_dump):
        return extract_sql_from_agent_response(model_dump())

    rich_component = getattr(raw_response, "rich_component", None)
    if rich_component is not None:
        sql = extract_sql_from_agent_response(rich_component)
        if sql:
            return sql

    simple_component = getattr(raw_response, "simple_component", None)
    if simple_component is not None:
        sql = extract_sql_from_agent_response(simple_component)
        if sql:
            return sql

    return None


def _canonicalize_known_question_sql(question: str, sql: str) -> tuple[str, bool]:
    entry, source = match_question_to_catalog_entry(question)
    if entry is None or source != "direct_catalog_match":
        return sql, False
    canonical_sql = str(entry["sql"]).strip()
    if canonical_sql == sql.strip():
        return sql, False
    logger.info(
        "agent_sql_canonicalized",
        extra={
            "event": "agent_sql_canonicalized",
            "stage": "agent_canonicalization",
            "question": question,
            "preview": canonical_sql[:300],
        },
    )
    return canonical_sql, True


def _recover_known_question_sql(question: str) -> str | None:
    entry, source = match_question_to_catalog_entry(question)
    if entry is None or source != "direct_catalog_match":
        return None
    return str(entry["sql"]).strip()
