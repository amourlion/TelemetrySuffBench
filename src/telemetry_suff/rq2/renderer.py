"""Fail-closed, manifest-driven RQ2 renderer."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .factors import FactorManifest, load_manifest
from .masks import Mask
from .schema import RenderedTrace


def _leaf_paths(value: Any, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        return sum((_leaf_paths(child, f"{prefix}.{key}" if prefix else key) for key, child in value.items()), [])
    if isinstance(value, list):
        if prefix in {"events", "events.*.parent_event_ids", "events.*.dependency_event_ids"}:
            if prefix == "events":
                return sum((_leaf_paths(child, "events.*") for child in value), [])
            return [prefix]
        return [prefix]
    return [prefix]


def _event_path(path: str) -> str:
    return f"events.*.{path}"


def _get_nested(event: dict, path: str) -> tuple[bool, Any]:
    current: Any = event
    parts = path.split(".")
    for index, key in enumerate(parts):
        if not isinstance(current, dict) or key not in current:
            # Canonical workflow attributes intentionally contain dots in
            # their literal keys (for example ``workflow.reference``).
            literal = ".".join(parts[index:])
            if isinstance(current, dict) and literal in current:
                return True, current[literal]
            return False, None
        current = current[key]
    return True, current


def _set_nested(target: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    current = target
    for index, key in enumerate(parts[:-1]):
        if key == "workflow":
            current[".".join(parts[index:])] = value
            return
        current = current.setdefault(key, {})
    current[parts[-1]] = value


def render_trace(trace: dict, mask: Mask, manifest: FactorManifest | None = None) -> RenderedTrace:
    manifest = manifest or load_manifest()
    enabled = set(mask.enabled_factors)
    known = manifest.known_paths
    private_roots = {path.split(".", 1)[0] for path in manifest.private_never_visible}
    unknown = sorted({
        path for path in _leaf_paths(trace)
        if path not in known and path.split(".", 1)[0] not in private_roots
    })
    candidate_ids = tuple(str(event["event_id"]) for event in trace["events"])
    rendered_events: list[dict] = []
    for event in trace["events"]:
        output: dict[str, Any] = {}
        for absolute_path in sorted(path for path in known if path.startswith("events.*.")):
            relative = absolute_path[len("events.*."):]
            exists, value = _get_nested(event, relative)
            if not exists:
                continue
            if absolute_path in manifest.always_visible:
                visible = value
            elif absolute_path in manifest.ignored_known_fields:
                continue
            else:
                factor = manifest.field_to_factor[absolute_path]
                if factor in enabled:
                    visible = value
                else:
                    strategy = manifest.factors[factor].deletion
                    if strategy == "delete":
                        continue
                    visible = None if strategy == "null" else manifest.redaction
            _set_nested(output, relative, visible)
        rendered_events.append(output)
    payload = {
        "events": rendered_events,
        "candidate_event_ids": list(candidate_ids),
    }
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    components = tuple(sorted({
        str(e.get("component_type")) for e in rendered_events
        if e.get("component_type") not in {None, manifest.redaction}
    }))
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return RenderedTrace(
        trace_id=trace["trace_id"], mask_id=mask.mask_id, content=content,
        render_hash=digest, candidate_event_ids=candidate_ids,
        candidate_components=components, unknown_fields=tuple(unknown),
    )
