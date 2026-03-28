from __future__ import annotations

import asyncio
import inspect

from app.config import settings
from app.memory_seed_examples import SEED_EXAMPLES
from app.memory_store import load_seed_records, save_seed_records
from vanna_setup import build_tool_context, get_agent_components


async def seed_vanna_memory() -> int:
    existing_records = load_seed_records(settings.memory_seed_path)
    existing_questions = {record["question"] for record in existing_records}
    new_records = [record for record in SEED_EXAMPLES if record["question"] not in existing_questions]

    if new_records:
        save_seed_records(settings.memory_seed_path, existing_records + new_records)

    components = get_agent_components()
    user = components.user_resolver.get_default_user()
    tool_context = build_tool_context(components.memory, user)

    seeded_count = 0
    for record in SEED_EXAMPLES:
        try:
            result = components.memory.save_tool_usage(
                question=record["question"],
                tool_name="run_sql",
                args={"sql": record["sql"]},
                context=tool_context,
                success=True,
                metadata={"seeded": True},
            )
            if inspect.isawaitable(result):
                await result
            seeded_count += 1
        except Exception:
            continue

    return seeded_count


def main() -> None:
    seeded_count = asyncio.run(seed_vanna_memory())
    total_examples = len(SEED_EXAMPLES)
    print(f"Seed manifest contains {total_examples} examples.")
    print(f"Saved {seeded_count} examples into DemoAgentMemory.")


if __name__ == "__main__":
    main()
