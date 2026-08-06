#!/usr/bin/env python3
"""Score normalized RQ2 predictions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from telemetry_suff.rq2.interactions import contrasts
from telemetry_suff.rq2.metrics import answer_behavior, evaluate
from telemetry_suff.rq2.protocol import INSUFFICIENT, parse_prediction


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--jobs", type=Path, default=Path("outputs/private/rq2_confirmation_11mask.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("outputs/derived/rq2_metrics.json"))
    args = parser.parse_args()
    jobs, supplied = read_jsonl(args.jobs), read_jsonl(args.predictions)
    by_id = {row.get("task_id", row.get("request_id")): row for row in supplied}
    predictions = []
    invalid_default = {
        "fault_present": False, "fault_type": None,
        "answerability": INSUFFICIENT,
        "origin_component": None, "origin_event_id": None,
    }
    for job in jobs:
        row = by_id.get(job["task_id"], {})
        value = row.get("prediction")
        parse_valid = True
        try:
            parse_prediction(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            value, parse_valid = invalid_default, False
        predictions.append({"task_id": job["task_id"], "prediction": value, "parse_valid": parse_valid})
    by_mask = evaluate(jobs, predictions)
    result = {"metrics_by_mask": by_mask, "contrasts": contrasts(by_mask), "answer_behavior": answer_behavior(jobs, predictions)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
