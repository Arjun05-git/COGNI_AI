from __future__ import annotations

import json
import sys

from fastapi.testclient import TestClient

import main


def main_inspect() -> None:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        raise SystemExit('Usage: python inspect_query.py "Your question here"')

    client = TestClient(main.app)
    response = client.post("/chat", json={"question": question})
    body = response.json()
    debug = body.get("debug", {}) if isinstance(body, dict) else {}

    output = {
        "status_code": response.status_code,
        "question": question,
        "message": body.get("message"),
        "sql_query": body.get("sql_query"),
        "row_count": body.get("row_count"),
        "source": debug.get("source"),
        "stage": debug.get("stage"),
        "detail": debug.get("detail"),
        "method_name": debug.get("method_name"),
        "raw_preview": debug.get("raw_preview"),
        "error": body.get("error"),
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main_inspect()
