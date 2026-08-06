"""Information-integrity checks for causal witnesses.

The recovery algorithm reads only the rendered telemetry. Gold labels are used
afterwards solely to score whether the independently recovered event is right.
"""

from __future__ import annotations

import json
from typing import Any

from .masks import Mask
from .schema import RenderedTrace

RECOVERY_FACTORS = frozenset({"D", "P", "V"})


def _structured(event: dict) -> dict:
    value = (event.get("output") or {}).get("structured")
    return value if isinstance(value, dict) else {}


def _parse_registry(value: Any) -> dict[str, str]:
    mappings: dict[str, str] = {}
    if not isinstance(value, str):
        return mappings
    for clause in value.split(";"):
        if "->" in clause:
            key, target = clause.split("->", 1)
            mappings[key] = target
    return mappings


def recover_origin(rendered: RenderedTrace) -> tuple[str | None, str | None]:
    payload = json.loads(rendered.content)
    events = payload["events"]
    registry: dict[str, str] = {}
    expected: str | None = None
    for event in events:
        values = _structured(event)
        registry.update(_parse_registry(values.get("workflow.reference_map")))
        candidate = values.get("workflow.expected_target")
        if isinstance(candidate, str) and candidate != "<REDACTED>":
            expected = candidate
    if not registry or not expected:
        return None, None
    for event in events:
        reference = _structured(event).get("workflow.reference")
        if reference in registry and registry[reference] != expected:
            component = event.get("component_type")
            if component == "<REDACTED>":
                component = None
            return event.get("event_id"), component
    return None, None


def analyze_witness(trace: dict, mask: Mask, rendered: RenderedTrace) -> dict:
    labels = trace["labels"]
    if not labels["is_fault"]:
        return {
            "trace_id": trace["trace_id"], "mask_id": mask.mask_id,
            "witness_recoverable": True, "model_expected_to_succeed": None,
            "visible_witness_event_ids": [], "visible_witness_edges": [],
            "missing_factors": [], "recovered_origin_event_id": None,
            "recovered_origin_component": None,
        }
    recovered_id, recovered_component = recover_origin(rendered)
    required = set(RECOVERY_FACTORS) | {"I"}
    visible_edges = labels.get("propagation_edges", []) if "R" in mask.enabled_factors else []
    witness_ids = list(dict.fromkeys(labels.get("causal_witness_event_ids") or []))
    recoverable = (
        recovered_id == labels["origin_event_id"]
        and recovered_component == labels["origin_component"]
        and not (required - set(mask.enabled_factors))
    )
    return {
        "trace_id": trace["trace_id"], "mask_id": mask.mask_id,
        "witness_recoverable": recoverable,
        "model_expected_to_succeed": None,
        "visible_witness_event_ids": [event_id for event_id in witness_ids if event_id in rendered.candidate_event_ids],
        "visible_witness_edges": visible_edges,
        "missing_factors": sorted(required - set(mask.enabled_factors)),
        "recovered_origin_event_id": recovered_id,
        "recovered_origin_component": recovered_component,
    }
