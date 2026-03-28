from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_seed_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_seed_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")


def count_seed_records(path: Path) -> int:
    return len(load_seed_records(path))
