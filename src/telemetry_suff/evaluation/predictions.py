"""Strict structured-output validation and RQ1/RQ3 scoring."""
from __future__ import annotations
from typing import Any

REQUIRED = {"is_fault", "fault_type", "origin_component", "origin_event_id", "answerability", "confidence"}

def validate_prediction(prediction: Any, visible_event_ids: set[str]) -> str | None:
    if not isinstance(prediction, dict) or set(prediction) != REQUIRED:
        return "schema"
    if prediction["answerability"] not in {"ANSWERABLE", "INSUFFICIENT_EVIDENCE"}:
        return "answerability"
    if not isinstance(prediction["confidence"], (int, float)) or not 0 <= prediction["confidence"] <= 1:
        return "confidence"
    if prediction["answerability"] == "INSUFFICIENT_EVIDENCE":
        if any(prediction[key] is not None for key in ("fault_type", "origin_component", "origin_event_id")):
            return "abstention_fields"
    elif prediction["origin_event_id"] not in visible_event_ids:
        return "event_id"
    return None

def answerability_metrics(records: list[dict]) -> dict[str, float]:
    ambiguous = [r for r in records if not r["answerable"]]
    answerable = [r for r in records if r["answerable"]]
    false_attribution = sum(r["prediction"]["answerability"] == "ANSWERABLE" for r in ambiguous) / len(ambiguous) if ambiguous else 0.0
    unnecessary = sum(r["prediction"]["answerability"] == "INSUFFICIENT_EVIDENCE" for r in answerable) / len(answerable) if answerable else 0.0
    return {"false_attribution_rate": false_attribution, "unnecessary_abstention_rate": unnecessary}
