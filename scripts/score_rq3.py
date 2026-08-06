#!/usr/bin/env python3
"""Score normalized RQ3 predictions and optionally run clustered bootstrap."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from telemetry_suff.rq3.core import bootstrap, metrics, outcome, parse_prediction, read_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("outputs/derived/rq3_metrics.json"))
    parser.add_argument("--bootstrap", action="store_true")
    args = parser.parse_args()
    jobs = read_jsonl(args.jobs)
    supplied = {row["request_id"]: row for row in read_jsonl(args.predictions)}
    missing = {job["request_id"] for job in jobs} - set(supplied)
    if missing:
        raise ValueError(f"missing {len(missing)} request IDs")
    scored = []
    for job in jobs:
        value = supplied[job["request_id"]].get("prediction")
        prediction = parse_prediction(value, job)
        scored.append({**job, "prediction": prediction, "outcome": outcome(job, prediction)})
    report = {"metrics": metrics(scored)}
    if args.bootstrap:
        report["cluster_bootstrap"] = bootstrap(scored)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
