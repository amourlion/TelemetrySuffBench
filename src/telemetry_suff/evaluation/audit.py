"""Diagnostic audit for paired RQ1 predictions."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from math import sqrt
from pathlib import Path
from typing import Any


def _norm(value: Any) -> str:
    return str(value).casefold().strip()


def _safe_rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _audit_view(rows: list[dict[str, Any]], tasks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    prediction_types: Counter[str] = Counter()
    type_confusion: Counter[str] = Counter()
    component_visible = event_visible = jointly_visible = abstained = component_correct = event_correct = 0
    localization_n = 0
    placement: Counter[str] = Counter()
    for row in rows:
        task, prediction = tasks[row["task_id"]], row.get("prediction") or {}
        gold, view = task["labels"], task["view"]
        actual, predicted = bool(gold["is_fault"]), prediction.get("is_fault") is True
        if actual and predicted: tp += 1
        elif not actual and predicted: fp += 1
        elif not actual: tn += 1
        else: fn += 1
        prediction_types[str(prediction.get("fault_type"))] += 1
        type_confusion[f"{gold.get('fault_type')} -> {prediction.get('fault_type')}"] += 1
        if not actual:
            continue
        localization_n += 1
        events = view.get("events", [])
        ids = {event.get("event_id") for event in events}
        roles = {_norm(value) for event in events for value in (event.get("actor_id"), event.get("actor_role"), event.get("component_type")) if value is not None}
        has_component = gold.get("origin_component") is not None and _norm(gold["origin_component"]) in roles
        has_event = gold.get("origin_event_id") in ids
        if has_component:
            component_visible += 1
        if has_event:
            event_visible += 1
        if has_component and has_event:
            jointly_visible += 1
        if prediction.get("answerability") == "INSUFFICIENT_EVIDENCE" or prediction.get("origin_event_id") is None:
            abstained += 1
        selected = prediction.get("origin_event_id")
        if selected is not None:
            if _norm(prediction.get("origin_component")) == _norm(gold.get("origin_component")):
                component_correct += 1
            if selected == gold.get("origin_event_id"):
                event_correct += 1
            if selected == gold.get("origin_event_id"):
                placement["origin"] += 1
            elif selected in set(gold.get("symptom_event_ids") or []):
                placement["symptom"] += 1
            elif selected == gold.get("terminal_failure_event_id"):
                placement["terminal"] += 1
            else:
                placement["other"] += 1
    n = len(rows)
    precision, recall = _safe_rate(tp, tp + fp), _safe_rate(tp, tp + fn)
    specificity = _safe_rate(tn, tn + fp)
    denominator = sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return {
        "n": n, "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision": precision, "recall": recall, "specificity": specificity,
        "balanced_accuracy": None if recall is None or specificity is None else (recall + specificity) / 2,
        "mcc": ((tp * tn - fp * fn) / denominator) if denominator else None,
        "predicted_fault_rate": _safe_rate(tp + fp, n),
        "fault_type_prediction_counts": dict(prediction_types),
        "fault_type_confusion": dict(type_confusion),
        "n_fault_localization": localization_n,
        "origin_component_visible_rate": _safe_rate(component_visible, localization_n),
        "origin_event_visible_rate": _safe_rate(event_visible, localization_n),
        "answerable_rate": _safe_rate(jointly_visible, localization_n),
        "component_accuracy": _safe_rate(component_correct, localization_n),
        "component_accuracy_given_visible": _safe_rate(component_correct, component_visible),
        "step_top1": _safe_rate(event_correct, localization_n),
        "step_top1_given_visible": _safe_rate(event_correct, event_visible),
        "model_abstention_rate": _safe_rate(abstained, localization_n),
        "selected_event_placement": dict(placement),
    }


def audit(predictions: Path, queue: Path, output: Path) -> dict[str, Any]:
    tasks = {item["task_id"]: item for item in (json.loads(line) for line in queue.read_text().splitlines() if line)}
    rows = {item["task_id"]: item for item in (json.loads(line) for line in predictions.read_text().splitlines() if line)}
    by_view: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows.values():
        if row["task_id"] in tasks:
            by_view[row["view_id"]].append(row)
    report = {"n_expected": len(tasks), "n_unique_predictions": len(rows), "by_view": {name: _audit_view(items, tasks) for name, items in sorted(by_view.items())}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report
