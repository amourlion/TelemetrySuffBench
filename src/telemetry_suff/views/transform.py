"""Deterministic telemetry view transformations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from telemetry_suff.schema import CanonicalTrace

SIGNALS = (
    "identity",
    "decision_content",
    "tool_inputs",
    "observations",
    "memory_retrieval_provenance",
    "relations",
)
SIGNAL_BITS = {name: 1 << index for index, name in enumerate(SIGNALS)}


def visible_signal_groups(mask: int) -> list[str]:
    if not 0 <= mask < 64:
        raise ValueError("signal mask must be in [0, 63]")
    return [name for name in SIGNALS if mask & SIGNAL_BITS[name]]


def _present(value: Any) -> Any:
    return "<REDACTED>" if value is not None else None


def _base_event(event: Any) -> dict[str, Any]:
    return {"event_id": event.event_id, "step_index": event.step_index, "event_type": event.event_type, "status": event.status}


def build_mask_view(trace: CanonicalTrace, mask: int) -> dict[str, Any]:
    """Build a minimal, deterministic view using the specified six-bit mask."""
    groups = visible_signal_groups(mask)
    events: list[dict[str, Any]] = []
    for source in trace.events:
        event = _base_event(source)
        if "identity" in groups:
            event.update(actor_id=source.actor_id, actor_role=source.actor_role, display_name=source.display_name, component_type=source.component_type)
        if "decision_content" in groups:
            event.update(input=deepcopy(source.input), output=deepcopy(source.output))
        if "tool_inputs" in groups:
            event["tool"] = {"name": source.tool.get("name"), "arguments": deepcopy(source.tool.get("arguments"))}
        if "observations" in groups:
            event.update(tool_result=deepcopy(source.tool.get("result")), exception=source.exception)
        if "memory_retrieval_provenance" in groups:
            event.update(retrieval=deepcopy(source.retrieval), memory=deepcopy(source.memory))
        if "relations" in groups:
            event.update(parent_event_ids=source.parent_event_ids, dependency_event_ids=source.dependency_event_ids)
        events.append(event)
    return {"trace_id": trace.trace_id, "view_family": "signal_mask", "signal_mask": mask, "visible_signal_groups": groups, "events": events}


def build_coarse_view(trace: CanonicalTrace, family: str) -> dict[str, Any]:
    """Build documented RQ1 coarse views without inferring missing source fields."""
    if family == "full":
        result = trace.model_dump(mode="json", exclude={"labels", "metadata"})
        result["view_family"] = family
        return result
    if family == "structural":
        return build_mask_view(trace, 32) | {"view_family": family}
    if family == "metadata":
        view = build_mask_view(trace, 1 | 4 | 8 | 32)
        for event in view["events"]:
            event.pop("tool_result", None)
            event.pop("exception", None)
        return view | {"view_family": family}
    if family == "content_redacted":
        view = build_mask_view(trace, 63)
        for event in view["events"]:
            for field in ("input", "output", "retrieval", "memory", "tool", "tool_result", "exception"):
                if field in event:
                    event[field] = _redact(event[field])
        return view | {"view_family": family}
    if family in {"otel", "openinference"}:
        # Conservative compatibility views only expose unambiguous generic fields.
        view = build_mask_view(trace, 1 | 4 | 8 | 32)
        return view | {"view_family": family, "compatibility": "conservative"}
    raise ValueError(f"unknown coarse view family: {family}")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return _present(value)
