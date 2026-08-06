"""Paired RQ1 metrics over model predictions and canonical labels."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _normalise(field: str, value: Any) -> Any:
    return value.casefold().strip() if field == "origin_component" and isinstance(value, str) else value


def _accuracy(records: list[dict[str, Any]], labels: dict[str, dict[str, Any]], field: str) -> float | None:
    scored = [item for item in records if labels[item["task_id"]].get(field) is not None]
    if not scored:
        return None
    return sum(_normalise(field, item["prediction"].get(field)) == _normalise(field, labels[item["task_id"]][field]) for item in scored) / len(scored)


def _macro_f1(records: list[dict[str, Any]], labels: dict[str, dict[str, Any]], field: str) -> float | None:
    scored = [item for item in records if labels[item["task_id"]].get(field) is not None]
    if not scored:
        return None
    classes = {_normalise(field, labels[item["task_id"]][field]) for item in scored}
    f1s: list[float] = []
    for value in classes:
        true_positive = sum(_normalise(field, item["prediction"].get(field)) == value and _normalise(field, labels[item["task_id"]][field]) == value for item in scored)
        false_positive = sum(_normalise(field, item["prediction"].get(field)) == value and _normalise(field, labels[item["task_id"]][field]) != value for item in scored)
        false_negative = sum(_normalise(field, item["prediction"].get(field)) != value and _normalise(field, labels[item["task_id"]][field]) == value for item in scored)
        denominator = 2 * true_positive + false_positive + false_negative
        f1s.append((2 * true_positive / denominator) if denominator else 0.0)
    return sum(f1s) / len(f1s)


def _detection_f1(records: list[dict[str, Any]], labels: dict[str, dict[str, Any]]) -> float | None:
    scored = [item for item in records if labels[item["task_id"]].get("is_fault") is not None]
    if not scored or len({labels[item["task_id"]]["is_fault"] for item in scored}) < 2:
        return None
    true_positive = sum(item["prediction"].get("is_fault") is True and labels[item["task_id"]]["is_fault"] is True for item in scored)
    false_positive = sum(item["prediction"].get("is_fault") is True and labels[item["task_id"]]["is_fault"] is False for item in scored)
    false_negative = sum(item["prediction"].get("is_fault") is not True and labels[item["task_id"]]["is_fault"] is True for item in scored)
    denominator = 2 * true_positive + false_positive + false_negative
    return (2 * true_positive / denominator) if denominator else 0.0


def _metrics(records: list[dict[str, Any]], labels: dict[str, dict[str, Any]], expected: int, input_rows: int | None = None) -> dict[str, Any]:
    valid = [item for item in records if item.get("prediction") and item["task_id"] in labels]
    fault_values = {labels[item["task_id"]]["is_fault"] for item in valid if labels[item["task_id"]].get("is_fault") is not None}
    return {
        "n_expected": expected,
        "n_predictions": input_rows if input_rows is not None else len(records),
        "n_unique_predictions": len(records),
        "n_valid": len(valid),
        "n_errors": sum(item.get("error") is not None for item in records),
        "n_missing": max(expected - len({item["task_id"] for item in records}), 0),
        "valid_rate": len(valid) / expected if expected else None,
        "detection_accuracy": _accuracy(valid, labels, "is_fault") if len(fault_values) > 1 else None,
        "detection_f1": _detection_f1(valid, labels),
        "fault_type_accuracy": _accuracy(valid, labels, "fault_type"),
        "fault_type_macro_f1": _macro_f1(valid, labels, "fault_type"),
        "component_accuracy": _accuracy(valid, labels, "origin_component"),
        "component_macro_f1": _macro_f1(valid, labels, "origin_component"),
        "step_top1": _accuracy(valid, labels, "origin_event_id"),
    }


def evaluate(predictions: Path, queue: Path, output: Path) -> dict[str, Any]:
    tasks = [json.loads(line) for line in queue.read_text(encoding="utf-8").splitlines() if line]
    labels = {item["task_id"]: item["labels"] for item in tasks}
    expected_by_view: dict[str, int] = defaultdict(int)
    for item in tasks:
        expected_by_view[item["view_id"]] += 1
    raw_records = [json.loads(line) for line in predictions.read_text(encoding="utf-8").splitlines() if line]
    task_by_id = {item["task_id"]: item for item in tasks}
    raw_records = [
        {
            **item,
            "task_id": item.get("task_id", item.get("request_id")),
            "view_id": item.get("view_id") or task_by_id.get(item.get("task_id", item.get("request_id")), {}).get("view_id", "unknown"),
            "prediction": item.get("prediction") if isinstance(item.get("prediction"), dict) else {},
        }
        for item in raw_records
    ]
    # If duplicate identifiers are supplied, the final normalized record wins.
    records_by_task = {item["task_id"]: item for item in raw_records}
    records = list(records_by_task.values())
    records_by_view: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in records:
        records_by_view[item.get("view_id", "unknown")].append(item)
    report: dict[str, Any] = _metrics(records, labels, len(tasks), input_rows=len(raw_records))
    report["by_view"] = {
        view_id: _metrics(records_by_view[view_id], labels, expected)
        for view_id, expected in sorted(expected_by_view.items())
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
