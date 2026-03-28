# Clinic NL2SQL Backend

This project implements the interview assignment as a clean, production-shaped backend that converts English questions into SQLite queries using Vanna 2.0, validates the SQL for safety, runs it against a clinic database, and returns structured API responses with optional chart payloads.

## Stack

- Python 3.10+
- FastAPI
- SQLite
- Vanna 2.0
- Configurable LLM provider:
  - Google Gemini via `GeminiLlmService`
  - Groq via Vanna's `OpenAILlmService` against Groq's OpenAI-compatible API
  - Ollama via `OllamaLlmService`
- Plotly

## Project Layout

```text
.
|-- app/
|   |-- charts.py
|   |-- config.py
|   |-- db.py
|   |-- logging_utils.py
|   |-- memory_seed_examples.py
|   |-- memory_store.py
|   |-- middleware.py
|   |-- nl2sql.py
|   |-- question_bank.py
|   |-- schemas.py
|   |-- semantic_catalog.py
|   `-- sql_safety.py
|-- clinic.db
|-- index.html
|-- main.py
|-- README.md
|-- RESULTS.md
|-- requirements.txt
|-- run_assignment_tests.py
|-- seed_memory.py
|-- setup_database.py
`-- vanna_setup.py
```

## Environment Variables

Copy [.env.example](/c:/Users/rosha/Downloads/Arjun/.env.example) to `.env` and choose one provider.

Groq:

```env
VANNA_LLM_PROVIDER=groq
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_BASE_URL=https://api.groq.com/openai/v1
```

Gemini:

```env
VANNA_LLM_PROVIDER=gemini
GOOGLE_API_KEY=your-google-ai-studio-key
GEMINI_MODEL=gemini-2.5-flash
```

Ollama:

```env
VANNA_LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1
OLLAMA_HOST=http://localhost:11434
```

API keys must never be hardcoded.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create the SQLite database:

```bash
python setup_database.py
```

4. Seed the local memory manifest and DemoAgentMemory:

```bash
python seed_memory.py
```

5. Start the API:

```bash
uvicorn main:app --port 8000 --reload
```

## API

### `GET /health`

Returns application, database, and memory status.

Example response:

```json
{
  "status": "ok",
  "database": "connected",
  "agent_memory_items": 22,
  "llm_provider": "groq"
}
```

### `POST /chat`

Request:

```json
{
  "question": "Show the top 5 patients by spending"
}
```

Response shape:

```json
{
  "message": "Found 5 rows for \"Show the top 5 patients by spending\".",
  "sql_query": "SELECT ...",
  "columns": ["first_name", "last_name", "total_spending"],
  "rows": [["Aarav", "Sharma", 12450.75]],
  "row_count": 5,
  "chart": {
    "data": [],
    "layout": {}
  },
  "chart_type": "bar",
  "error": null
}
```

## Architecture Overview

The request flow is:

1. FastAPI validates the incoming question with Pydantic.
2. The Vanna 2.0 setup in [vanna_setup.py](/c:/Users/rosha/Downloads/Arjun/vanna_setup.py) builds:
   - one provider-specific LLM service:
     - `GeminiLlmService`, or
     - `OpenAILlmService` for Groq, or
     - `OllamaLlmService`
   - `ToolRegistry`
   - `RunSqlTool`
   - `VisualizeDataTool`
   - `SaveQuestionToolArgsTool`
   - `SearchSavedCorrectToolUsesTool`
   - `DemoAgentMemory`
   - `SqliteRunner`
   - `Agent`
3. [main.py](/c:/Users/rosha/Downloads/Arjun/main.py) asks the agent for SQL.
4. The generated SQL is validated locally:
   - only `SELECT` and CTE-based `SELECT`
   - no DML/DDL/system table access
   - no multi-statement execution
5. The validated query runs against `clinic.db`.
6. The API returns structured rows plus a Plotly chart when the result is chart-friendly.
7. For the fixed 20 assignment prompts, the app also includes a transparent semantic catalog plus fallback mapping so the system can recover if the primary agent path fails or the provider quota is exhausted.

## Notes On Safety And Reliability

- The API rejects dangerous SQL before execution.
- Empty questions are rejected by request validation.
- Database and agent errors return friendly structured error payloads.
- The dataset is deterministic because [setup_database.py](/c:/Users/rosha/Downloads/Arjun/setup_database.py) uses a fixed random seed.
- The memory seed script is idempotent for the local manifest file used by the app.
- The app includes an assignment-oriented fallback for the fixed 20 evaluation prompts. This should be disclosed honestly if used during testing.
- Gemini free-tier quotas can cause fallback activation during repeated testing. Groq is often the most practical hosted backup for demo day.

## Automated Assignment Test Run

After dependencies are installed and `.env` is configured, you can generate [RESULTS.md](/c:/Users/rosha/Downloads/Arjun/RESULTS.md) automatically:

```bash
python run_assignment_tests.py
```

## SQL And Response Audit

To verify that the canonical assignment SQL is safe, executable, and consistent with what `/chat` returns, run:

```bash
python audit_assignment_flow.py
```

This generates `AUDIT.md` with:
- schema snapshot
- canonical SQL execution checks
- `/chat` response status and source
- SQL match against the canonical assignment query
- returned column and row-count verification

## Inspect One Query

To inspect one question end to end, including the raw agent preview and whether it used normal agent flow, canonicalization, or recovery, run:

```bash
python inspect_query.py "Show me appointments for last month"
```

## Assignment Deliverables Included

- `setup_database.py`
- `seed_memory.py`
- `vanna_setup.py`
- `main.py`
- `requirements.txt`
- `README.md`
- `RESULTS.md`
- `clinic.db` after running `python setup_database.py`

## Reviewer Runbook

```bash
pip install -r requirements.txt
python setup_database.py
python seed_memory.py
uvicorn main:app --port 8000
```
