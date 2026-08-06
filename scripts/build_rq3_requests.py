#!/usr/bin/env python3
"""Build RQ3 P0 and policy-variant requests without an inference client."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from telemetry_suff.rq3.core import build_queues, read_jsonl, sha, write_jsonl
from telemetry_suff.rq3.policies import POLICIES, apply_policy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-label", default="MODEL-ID-TO-BE-SUPPLIED")
    args = parser.parse_args()
    root = Path(".")
    summary = {"p0": build_queues(root, args.model_label)}
    for split in ("discovery", "confirmation"):
        base_requests = {row["request_id"]: row for row in read_jsonl(root / f"outputs/requests/rq3_{split}_p0.jsonl")}
        base_jobs = read_jsonl(root / f"data/rq3/manifests/rq3_{split}_logical_jobs.jsonl")
        for short, spec in POLICIES.items():
            logical, requests = [], {}
            for job in base_jobs:
                payload = apply_policy(base_requests[job["request_id"]]["model_visible_payload"], spec["policy"])
                logical_id = sha({"prompt": spec["id"], "base": job["logical_job_id"]})
                request_id = sha({"prompt": spec["id"], "base_request": job["request_id"]})
                logical.append({**job, "logical_job_id": logical_id, "request_id": request_id, "prompt_id": spec["id"]})
                requests.setdefault(request_id, {"request_id": request_id, "prompt_id": spec["id"], "model": args.model_label, "logical_job_ids": [], "model_visible_payload": payload})["logical_job_ids"].append(logical_id)
            write_jsonl(root / f"outputs/private/rq3_{split}_{short}_logical.jsonl", logical)
            write_jsonl(root / f"outputs/requests/rq3_{split}_{short}.jsonl", requests.values())
            summary[f"{split}_{short}"] = {"logical": len(logical), "requests": len(requests)}
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
