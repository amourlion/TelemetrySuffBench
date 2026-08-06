"""RQ2 primary, attribution, and selective metrics."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .causal_stage import causal_stage
from .protocol import ANSWERABLE, Prediction, parse_prediction
from .validator import validate_prediction


def _f1(y_true: list[bool], y_pred: list[bool]) -> float:
    tp = sum(a and b for a, b in zip(y_true, y_pred))
    fp = sum(not a and b for a, b in zip(y_true, y_pred))
    fn = sum(a and not b for a, b in zip(y_true, y_pred))
    return 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0


def _balanced_accuracy(y_true: list[bool], y_pred: list[bool]) -> float:
    rates = []
    for label in (False, True):
        indices = [i for i, value in enumerate(y_true) if value == label]
        if indices:
            rates.append(sum(y_pred[i] == label for i in indices) / len(indices))
    return sum(rates) / len(rates)


def _macro_f1(y_true: list[str], y_pred: list[str], labels: list[str]) -> float:
    scores = []
    for label in labels:
        truth = [value == label for value in y_true]
        predicted = [value == label for value in y_pred]
        scores.append(_f1(truth, predicted))
    return sum(scores) / len(scores) if scores else 0.0


def evaluate_mask(jobs: list[dict], prediction_rows: list[dict]) -> dict[str, Any]:
    predictions = {row["task_id"]: parse_prediction(row.get("prediction", row)) for row in prediction_rows}
    parse_valid_by_task = {row["task_id"]: row.get("parse_valid", True) for row in prediction_rows}
    y_true, y_pred = [], []
    fault_types = sorted({job["gold_fault_type"] for job in jobs if job["gold_fault_type"]})
    valid = 0
    faults = [job for job in jobs if job["gold_fault_present"]]
    answered_faults = 0
    correct_component = correct_origin = 0
    attribution = Counter()
    audit = Counter()
    validation_errors: dict[str, list[str]] = {}
    classification_invalid: set[str] = set()
    for job in jobs:
        prediction = predictions[job["task_id"]]
        errors = validate_prediction(
            prediction,
            job["candidate_event_ids"],
            job["candidate_components"],
            job.get("candidate_fault_types"),
        )
        if not parse_valid_by_task[job["task_id"]]:
            errors = [*errors, "unparseable_output"]
        if errors:
            audit.update(errors)
            validation_errors[job["task_id"]] = errors
        else:
            valid += 1
        if (
            not parse_valid_by_task[job["task_id"]]
            or "fault_type_not_candidate" in errors
            or "clean_prediction_must_have_null_fault_type" in errors
        ):
            classification_invalid.add(job["task_id"])
        y_true.append(job["gold_fault_present"])
        y_pred.append(prediction.fault_present)
        if job["gold_fault_present"]:
            answered = prediction.answerability == ANSWERABLE
            answered_faults += answered
            correct_component += answered and not errors and prediction.origin_component == job["gold_origin_component"]
            correct_origin += answered and not errors and prediction.origin_event_id == job["gold_origin_event_id"]
            attribution[causal_stage(job, prediction.origin_event_id if answered and not errors else None)] += 1
    invalid_label = "__invalid_or_unclassified__"
    fault_gold = [job["gold_fault_type"] for job in faults]
    fault_predicted = [
        (
            predictions[job["task_id"]].fault_type
            if job["task_id"] not in classification_invalid
            else invalid_label
        )
        for job in faults
    ]
    conditional_fault_macro_f1 = _macro_f1(fault_gold, fault_predicted, fault_types)
    fault_type_per_class = {}
    for fault_type in fault_types:
        truth = [value == fault_type for value in fault_gold]
        predicted = [value == fault_type for value in fault_predicted]
        tp = sum(actual and guess for actual, guess in zip(truth, predicted))
        fp = sum(not actual and guess for actual, guess in zip(truth, predicted))
        fn = sum(actual and not guess for actual, guess in zip(truth, predicted))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        fault_type_per_class[fault_type] = {
            "support": sum(truth),
            "predicted": sum(predicted),
            "precision": precision,
            "recall": recall,
            "f1": _f1(truth, predicted),
        }
    fault_type_confusion = Counter(
        f"{gold} -> {predicted}"
        for gold, predicted in zip(fault_gold, fault_predicted)
    )

    joint_predicted = [
        (
            predictions[job["task_id"]].fault_type
            if (
                job["task_id"] not in classification_invalid
                and predictions[job["task_id"]].fault_present
            )
            else invalid_label
        )
        for job in jobs
    ]
    joint_fault_macro_f1 = _macro_f1(
        [job["gold_fault_type"] if job["gold_fault_present"] else "__clean__" for job in jobs],
        joint_predicted,
        fault_types,
    )

    end_to_end_gold = [
        job["gold_fault_type"] if job["gold_fault_present"] else "__clean__"
        for job in jobs
    ]
    end_to_end_predicted = []
    for job in jobs:
        prediction = predictions[job["task_id"]]
        if job["task_id"] in classification_invalid:
            end_to_end_predicted.append(invalid_label)
        elif not prediction.fault_present:
            end_to_end_predicted.append("__clean__")
        else:
            end_to_end_predicted.append(prediction.fault_type or invalid_label)
    end_to_end_macro_f1 = _macro_f1(
        end_to_end_gold,
        end_to_end_predicted,
        ["__clean__", *fault_types],
    )
    return {
        "mask_id": jobs[0]["mask_id"], "n": len(jobs), "fault_n": len(faults),
        "detection_f1": _f1(y_true, y_pred),
        "balanced_accuracy": _balanced_accuracy(y_true, y_pred),
        "fault_macro_f1": conditional_fault_macro_f1,
        "fault_macro_f1_scope": "gold_fault_traces_only_closed_taxonomy",
        "fault_type_per_class": fault_type_per_class,
        "fault_type_confusion": dict(sorted(fault_type_confusion.items())),
        "joint_fault_macro_f1": joint_fault_macro_f1,
        "joint_fault_macro_f1_scope": "all_traces_detection_and_closed_taxonomy",
        "end_to_end_macro_f1": end_to_end_macro_f1,
        "end_to_end_macro_f1_scope": "clean_plus_closed_fault_taxonomy",
        "component_accuracy": correct_component / len(faults),
        "origin_step_top1": correct_origin / len(faults),
        "model_declared_answerable_rate": answered_faults / len(faults),
        "abstention_rate": 1 - answered_faults / len(faults),
        "causal_stage_attribution": {stage: attribution.get(stage, 0) / len(faults) for stage in ("origin", "activation", "first_visible_deviation", "symptom", "terminal", "other", "abstain")},
        "coverage": answered_faults / len(faults),
        "selective_localization_accuracy": correct_origin / answered_faults if answered_faults else 0.0,
        "valid_output_rate": valid / len(jobs),
        "audit_errors": dict(audit),
    }


def evaluate(jobs: list[dict], prediction_rows: list[dict]) -> list[dict]:
    jobs_by_mask: dict[str, list[dict]] = defaultdict(list)
    predictions_by_task = {row["task_id"]: row for row in prediction_rows}
    for job in jobs:
        jobs_by_mask[job["mask_id"]].append(job)
    return [
        evaluate_mask(mask_jobs, [predictions_by_task[job["task_id"]] for job in mask_jobs])
        for _, mask_jobs in sorted(jobs_by_mask.items())
    ]


def answer_behavior(jobs: list[dict], prediction_rows: list[dict]) -> dict[str, dict[str, int]]:
    """Describe answer/abstain behavior without asserting gold answerability."""
    predictions = {row["task_id"]: parse_prediction(row.get("prediction", row)) for row in prediction_rows}
    counts: dict[str, Counter] = defaultdict(Counter)
    for job in jobs:
        if not job["gold_fault_present"]:
            continue
        prediction = predictions[job["task_id"]]
        answered = prediction.answerability == ANSWERABLE
        success = answered and prediction.origin_event_id == job["gold_origin_event_id"]
        if success:
            category = "answers_correct_origin"
        elif answered:
            category = "answers_wrong_origin"
        else:
            category = "abstains"
        counts[job["mask_id"]][category] += 1
    return {mask_id: dict(value) for mask_id, value in sorted(counts.items())}
