from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question must not be empty.")
        return cleaned


class ChatResponse(BaseModel):
    message: str
    sql_query: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    chart: dict[str, Any] | None = None
    chart_type: str | None = None
    error: str | None = None
    debug: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    database: str
    agent_memory_items: int
    llm_provider: str
