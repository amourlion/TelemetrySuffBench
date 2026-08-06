"""Stable visible-observation fingerprints for ambiguity validation."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any


def canonical_json(value: Any) -> str:
    normalized = _normalize(value)
    return json.dumps(normalized, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(view: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(view).encode("utf-8")).hexdigest()


def structural_fingerprint(view: dict[str, Any]) -> str:
    events = [{key: event.get(key) for key in ("event_type", "actor_role", "status", "parent_event_ids", "dependency_event_ids", "tool")} for event in view["events"]]
    return fingerprint({"events": events})


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(unicodedata.normalize("NFC", value).split())
    if isinstance(value, float):
        return round(value, 10)
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value
