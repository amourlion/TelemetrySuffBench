"""Strict validation; illegal outputs are audited and never autocorrected."""

from __future__ import annotations

from .protocol import ANSWERABLE, INSUFFICIENT, Prediction


def validate_prediction(
    prediction: Prediction,
    candidate_event_ids: list[str],
    candidate_components: list[str],
    candidate_fault_types: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    errors: list[str] = []
    if prediction.answerability == INSUFFICIENT:
        if prediction.origin_component is not None or prediction.origin_event_id is not None:
            errors.append("insufficient_evidence_requires_null_origin")
    elif prediction.fault_present:
        if prediction.origin_component is None or prediction.origin_event_id is None:
            errors.append("answerable_fault_requires_origin")
    if not prediction.fault_present and (prediction.origin_component is not None or prediction.origin_event_id is not None):
        errors.append("clean_prediction_must_not_have_origin")
    if not prediction.fault_present and prediction.fault_type is not None:
        errors.append("clean_prediction_must_have_null_fault_type")
    if (
        prediction.fault_type is not None
        and candidate_fault_types is not None
        and prediction.fault_type not in candidate_fault_types
    ):
        errors.append("fault_type_not_candidate")
    if prediction.origin_event_id is not None and prediction.origin_event_id not in candidate_event_ids:
        errors.append("origin_event_id_not_visible")
    if prediction.origin_component is not None and prediction.origin_component not in candidate_components:
        errors.append("origin_component_not_candidate")
    return errors
