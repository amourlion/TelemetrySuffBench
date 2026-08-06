"""Canonical RQ2 model-output protocol."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

ANSWERABLE = "ANSWERABLE"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
R3_FAULT_TYPES = ("stale_reference_state", "wrong_reference_binding")


@dataclass(frozen=True)
class Prediction:
    fault_present: bool
    fault_type: str | None
    answerability: str
    origin_component: str | None
    origin_event_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fault_present": self.fault_present, "fault_type": self.fault_type,
            "answerability": self.answerability,
            "origin_component": self.origin_component,
            "origin_event_id": self.origin_event_id,
        }


def parse_prediction(value: str | dict[str, Any]) -> Prediction:
    raw = json.loads(value) if isinstance(value, str) else value
    if not isinstance(raw, dict):
        raise ValueError("prediction must be a JSON object")
    required = {"fault_present", "fault_type", "answerability", "origin_component", "origin_event_id"}
    if set(raw) != required:
        raise ValueError(f"prediction fields must be exactly {sorted(required)}")
    if not isinstance(raw["fault_present"], bool):
        raise ValueError("fault_present must be boolean")
    if raw["fault_type"] is not None and not isinstance(raw["fault_type"], str):
        raise ValueError("fault_type must be string or null")
    if raw["answerability"] not in {ANSWERABLE, INSUFFICIENT}:
        raise ValueError("invalid answerability")
    for field in ("origin_component", "origin_event_id"):
        if raw[field] is not None and not isinstance(raw[field], str):
            raise ValueError(f"{field} must be string or null")
    return Prediction(**raw)
