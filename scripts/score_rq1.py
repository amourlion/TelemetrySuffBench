#!/usr/bin/env python3
"""Score normalized RQ1 predictions."""

from __future__ import annotations

import argparse
from pathlib import Path

from telemetry_suff.evaluation.rq1 import evaluate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--jobs", type=Path, default=Path("outputs/private/rq1.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("outputs/derived/rq1_metrics.json"))
    args = parser.parse_args()
    print(evaluate(args.predictions, args.jobs, args.output))


if __name__ == "__main__":
    main()
