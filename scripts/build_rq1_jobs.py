#!/usr/bin/env python3
"""Build the six-view RQ1 public requests and private scoring manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from telemetry_suff.schema import CanonicalTrace
from telemetry_suff.views import build_coarse_view, fingerprint

ROOT = Path(".")
FAMILIES = ("full", "content_redacted", "metadata", "structural", "otel", "openinference")
FAULT_TYPES = ("stale_reference_state", "wrong_reference_binding")
COMPONENTS = ("agent", "delegation", "guard_rail", "llm_call", "memory", "planning", "reasoning", "retrieval", "tool_call")
SYSTEM = (
    "You diagnose AI-agent execution telemetry using only visible evidence. Use "
    "only the supplied candidate fault types, components, and event IDs. Return "
    "the required JSON object and do not infer hidden state."
)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    source = ROOT / "data/canonical/agenttelemetry_component_extension_v1_r3"
    public, private = [], []
    for path in sorted(source.glob("*.json")):
        trace = CanonicalTrace.model_validate_json(path.read_text(encoding="utf-8"))
        for family in FAMILIES:
            view = build_coarse_view(trace, family)
            view["observed_fingerprint"] = fingerprint(view)
            task_id = hashlib.sha256(f"{trace.trace_id}:{family}:{view['observed_fingerprint']}".encode()).hexdigest()
            event_ids = [event["event_id"] for event in view.get("events", [])]
            payload = {
                "instruction": (
                    "Determine whether a fault occurred, classify a fault using the "
                    "closed taxonomy, and localize the first component and visible "
                    "event that introduced it. Return INSUFFICIENT_EVIDENCE with null "
                    "origin fields when the visible evidence does not identify one origin."
                ),
                "candidate_fault_types": list(FAULT_TYPES),
                "candidate_components": list(COMPONENTS),
                "candidate_event_ids": event_ids,
                "output_schema": {
                    "is_fault": "boolean", "fault_type": "candidate fault type|null",
                    "origin_component": "candidate component|null",
                    "origin_event_id": "candidate event ID|null",
                    "answerability": "ANSWERABLE|INSUFFICIENT_EVIDENCE",
                    "confidence": "number in [0,1]",
                },
                "telemetry": view,
            }
            public.append({"request_id": task_id, "logical_task_ids": [task_id], "system": SYSTEM, "user": json.dumps(payload, sort_keys=True, separators=(",", ":"))})
            private.append({"task_id": task_id, "trace_id": trace.trace_id, "view_id": family, "labels": trace.labels.model_dump(mode="json"), "source_metadata": trace.metadata, "candidate_event_ids": event_ids})
    if len(public) != 1872:
        raise RuntimeError(f"expected 1,872 RQ1 requests, found {len(public)}")
    write_jsonl(ROOT / "outputs/requests/rq1.jsonl", public)
    write_jsonl(ROOT / "outputs/private/rq1.jsonl", private)
    print(json.dumps({"requests": len(public), "traces": 312, "views": len(FAMILIES)}))


if __name__ == "__main__":
    main()
