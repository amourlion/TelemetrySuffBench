"""Observational-equivalence classes induced by rendered factor masks."""

from __future__ import annotations

import hashlib
from collections import defaultdict

from .schema import RenderedTrace


def classify_equivalence(traces: list[dict], rendered: list[RenderedTrace]) -> list[dict]:
    trace_by_id = {trace["trace_id"]: trace for trace in traces}
    classes: dict[tuple[str, str], list[RenderedTrace]] = defaultdict(list)
    for item in rendered:
        classes[(item.mask_id, item.render_hash)].append(item)
    output: list[dict] = []
    for (mask_id, render_hash), members in sorted(classes.items()):
        source = [trace_by_id[item.trace_id] for item in members]
        fault_members = [trace for trace in source if trace["labels"]["is_fault"]]
        origins = sorted({trace["labels"]["origin_event_id"] for trace in fault_members})
        components = sorted({trace["labels"]["origin_component"] for trace in fault_members})
        has_clean = len(fault_members) != len(source)
        has_fault = bool(fault_members)
        if has_clean and has_fault:
            ambiguity = "detection_ambiguous"
        elif len(origins) > 1:
            ambiguity = "origin_ambiguous"
        elif len(origins) == 1:
            ambiguity = "unique_origin"
        else:
            ambiguity = "clean_only"
        class_id = "eq_" + hashlib.sha256(f"{mask_id}|{render_hash}".encode()).hexdigest()[:16]
        for item in members:
            trace = trace_by_id[item.trace_id]
            output.append({
                "trace_id": item.trace_id, "mask_id": mask_id,
                "equivalence_class_id": class_id,
                "candidate_origin_event_ids": origins,
                "candidate_origin_components": components,
                "gold_answerable": bool(trace["labels"]["is_fault"] and len(origins) == 1 and not has_clean),
                "ambiguity_type": ambiguity,
                "class_size": len(members),
            })
    return sorted(output, key=lambda row: (row["mask_id"], row["trace_id"]))


def mask_render_equivalence(rendered: list[RenderedTrace], trace_ids: set[str] | None = None) -> dict[str, list[str]]:
    by_mask: dict[str, dict[str, str]] = defaultdict(dict)
    for item in rendered:
        if trace_ids is None or item.trace_id in trace_ids:
            by_mask[item.mask_id][item.trace_id] = item.render_hash
    signature_groups: dict[tuple[tuple[str, str], ...], list[str]] = defaultdict(list)
    for mask_id, values in by_mask.items():
        signature_groups[tuple(sorted(values.items()))].append(mask_id)
    return {
        "group_" + hashlib.sha256(repr(signature).encode()).hexdigest()[:12]: sorted(masks)
        for signature, masks in signature_groups.items()
    }
