"""Frozen RQ2 design used by the released cross-model experiment."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .factors import FACTOR_ORDER
from .masks import Mask, mask_for
from .offline_analysis import load_traces


def rq2_masks() -> list[Mask]:
    """Return the fixed 11-mask panel in presentation order."""
    full = set(FACTOR_ORDER)
    panel = [mask_for(full)]
    panel.extend(mask_for(full - {factor}) for factor in FACTOR_ORDER)
    panel.extend(
        mask_for(factors)
        for factors in (
            {"I", "D", "P", "V"}, {"D", "P", "V"}, {"S", "V", "T"},
        )
    )
    if len(panel) != 11 or len({mask.mask_id for mask in panel}) != 11:
        raise AssertionError("RQ2 panel must contain exactly eleven unique masks")
    return panel


def build_confirmation_split(root: Path = Path(".")) -> list[str]:
    traces = load_traces(root / "data/canonical/agenttelemetry_component_extension_v1_r3")
    smoke = {
        line.strip() for line in (root / "data/splits/agenttelemetry_component_extension_v1_r3_smoke96.txt").read_text().splitlines()
        if line.strip()
    }
    all_ids = {trace["trace_id"] for trace in traces}
    if len(smoke) != 96 or not smoke <= all_ids:
        raise ValueError("frozen smoke96 split is invalid")
    confirmation = sorted(all_ids - smoke)
    if len(confirmation) != 216:
        raise ValueError("confirmation split must contain exactly 216 traces")
    groups: dict[str, set[str]] = {}
    for trace in traces:
        group = trace["metadata"].get("matched_group_id")
        if group:
            groups.setdefault(group, set()).add(trace["trace_id"])
    for group, ids in groups.items():
        if ids & smoke and ids & set(confirmation):
            raise ValueError(f"matched group split across discovery/confirmation: {group}")
    path = root / "data/splits/agenttelemetry_component_extension_v1_r3_rq2_confirmation216.txt"
    path.write_text("\n".join(confirmation) + "\n", encoding="utf-8")
    return confirmation


def validate_frozen_splits(root: Path = Path(".")) -> dict:
    traces = load_traces(root / "data/canonical/agenttelemetry_component_extension_v1_r3")
    by_id = {trace["trace_id"]: trace for trace in traces}
    smoke_ids = [line.strip() for line in (root / "data/splits/agenttelemetry_component_extension_v1_r3_smoke96.txt").read_text().splitlines() if line.strip()]
    confirmation_ids = build_confirmation_split(root)
    smoke, confirmation = [by_id[trace_id] for trace_id in smoke_ids], [by_id[trace_id] for trace_id in confirmation_ids]
    fault_smoke = [trace for trace in smoke if trace["labels"]["is_fault"]]
    component_counts = Counter(trace["labels"]["origin_component"] for trace in fault_smoke)
    if len(smoke) != 96 or len(fault_smoke) != 72 or len(smoke) - len(fault_smoke) != 24:
        raise ValueError("smoke96 must contain 72 fault and 24 clean traces")
    if set(component_counts.values()) != {8} or len(component_counts) != 9:
        raise ValueError("smoke96 must contain eight faults for each of nine origin components")
    for name, subset in (("discovery", smoke), ("confirmation", confirmation)):
        domains = {trace["metadata"]["domain"] for trace in subset}
        operators = {trace["metadata"]["delayed_operator"] for trace in subset if trace["labels"]["is_fault"]}
        components = {trace["labels"]["origin_component"] for trace in subset if trace["labels"]["is_fault"]}
        if len(domains) != 3 or len(operators) != 6 or len(components) != 9:
            raise ValueError(f"{name} lacks required domain/operator/component support")
    return {"discovery": {"traces": 96, "faults": 72, "clean": 24, "component_counts": dict(sorted(component_counts.items()))}, "confirmation": {"traces": 216, "faults": sum(trace["labels"]["is_fault"] for trace in confirmation), "clean": sum(not trace["labels"]["is_fault"] for trace in confirmation)}, "trace_overlap": 0, "matched_groups_split": 0, "domains": 3, "operators": 6, "origin_components": 9, "mask_count": len(rq2_masks())}
