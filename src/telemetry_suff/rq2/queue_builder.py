"""Build model prompts and private paired-evaluation manifests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .experiment_design import build_confirmation_split, rq2_masks, validate_frozen_splits
from .masks import Mask
from .offline_analysis import load_traces
from .protocol import R3_FAULT_TYPES
from .renderer import render_trace


def _prompt(
    rendered: str,
    candidate_ids: list[str],
    components: list[str],
    fault_types: list[str],
) -> str:
    payload = {
        "instruction": (
            "Diagnose the AI-agent execution using only visible telemetry. "
            "Determine whether a fault occurred and classify it using exactly one "
            "candidate_fault_type when supported; do not invent another fault type. "
            "For a clean trace, set fault_present=false and fault_type=null. Then "
            "identify the component and visible event that first introduced a fault. "
            "If the visible evidence does not support a unique origin, return "
            "INSUFFICIENT_EVIDENCE. Do not infer hidden state."
        ),
        "candidate_event_ids": candidate_ids,
        "candidate_components": components,
        "candidate_fault_types": fault_types,
        "rendered_telemetry": json.loads(rendered),
        "output_schema": {
            "fault_present": "boolean",
            "fault_type": "candidate fault type|null",
            "answerability": "ANSWERABLE|INSUFFICIENT_EVIDENCE",
            "origin_component": "candidate component|null",
            "origin_event_id": "candidate event ID|null",
        },
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_jobs(traces: list[dict], masks: list[Mask], split: str) -> list[dict]:
    components = sorted({trace["labels"]["origin_component"] for trace in traces if trace["labels"]["is_fault"]})
    observed_fault_types = {trace["labels"]["fault_type"] for trace in traces if trace["labels"].get("fault_type")}
    if not observed_fault_types.issubset(R3_FAULT_TYPES):
        raise ValueError(f"R3 trace contains an unknown fault type: {sorted(observed_fault_types - set(R3_FAULT_TYPES))}")
    fault_types = list(R3_FAULT_TYPES)
    jobs: list[dict] = []
    for mask in masks:
        for trace in traces:
            item = render_trace(trace, mask)
            labels = trace["labels"]
            causal = {"origin": labels.get("origin_event_id"), "activation": labels.get("activation_event_id"), "first_visible_deviation": labels.get("first_visible_deviation_event_id"), "symptom": (labels.get("symptom_event_ids") or [None])[0], "terminal": labels.get("terminal_failure_event_id")}
            task_id = hashlib.sha256(f"RQ2-v3|{split}|{mask.mask_id}|{item.trace_id}".encode()).hexdigest()
            job = {"task_id": task_id, "dataset": "agenttelemetry_component_extension_v1_r3", "rq": "RQ2", "design_version": "rq2_paired_16_v3_closed_fault_taxonomy", "split": split, "mask_id": mask.mask_id, "enabled_factors": list(mask.enabled_factors), "trace_id": item.trace_id, "gold_fault_present": labels["is_fault"], "gold_fault_type": labels.get("fault_type"), "gold_origin_component": labels.get("origin_component"), "gold_origin_event_id": labels.get("origin_event_id"), "gold_causal_positions": causal, "matched_group_id": trace["metadata"].get("matched_group_id") or trace["trace_id"], "rendered_telemetry": item.content, "renderer_version": mask.renderer_version, "render_hash": item.render_hash, "candidate_event_ids": list(item.candidate_event_ids), "candidate_components": components, "candidate_fault_types": fault_types}
            job["model_prompt"] = _prompt(item.content, job["candidate_event_ids"], components, fault_types)
            jobs.append(job)
    return jobs


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def build_all_queues(root: Path = Path(".")) -> dict[str, int]:
    validate_frozen_splits(root)
    traces = load_traces(root / "data/canonical/agenttelemetry_component_extension_v1_r3")
    by_id = {trace["trace_id"]: trace for trace in traces}
    smoke_ids = [line.strip() for line in (root / "data/splits/agenttelemetry_component_extension_v1_r3_smoke96.txt").read_text().splitlines() if line.strip()]
    panel = rq2_masks()
    discovery = build_jobs([by_id[trace_id] for trace_id in smoke_ids], panel, "discovery")
    confirmation = build_jobs([by_id[trace_id] for trace_id in build_confirmation_split(root)], panel, "confirmation")
    write_jsonl(root / "outputs/private/rq2_discovery_11mask.jsonl", discovery)
    write_jsonl(root / "outputs/private/rq2_confirmation_11mask.jsonl", confirmation)
    return {"discovery": len(discovery), "confirmation": len(confirmation), "total": len(discovery) + len(confirmation), "mask_count": len(panel)}
