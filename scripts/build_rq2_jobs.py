#!/usr/bin/env python3
"""Build the released RQ2 11-mask requests."""

from __future__ import annotations

import json
from pathlib import Path

from telemetry_suff.rq2.queue_builder import build_all_queues

ROOT = Path(".")
SYSTEM = (
    "You diagnose AI-agent execution telemetry using only visible evidence. "
    "Follow the candidate taxonomy and origin lists in the user payload. Return "
    "only the required JSON object and do not infer hidden state."
)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    counts = build_all_queues(ROOT)
    for split in ("discovery", "confirmation"):
        private_path = ROOT / f"outputs/private/rq2_{split}_11mask.jsonl"
        jobs = read_jsonl(private_path)
        requests = [
            {"request_id": job["task_id"], "logical_task_ids": [job["task_id"]], "system": SYSTEM, "user": job["model_prompt"]}
            for job in jobs
        ]
        write_jsonl(ROOT / f"outputs/requests/rq2_{split}_11mask.jsonl", requests)
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
