#!/usr/bin/env python3
"""Offline integrity and shortcut gates for component-extension R2/R3.

R3 deliberately separates latent origin, activation, the first wrong target
value, the task-invariant symptom, and terminal verification.  This script is
an offline gate: it must pass before any model/API evaluation is permitted.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

COMPONENT_WORDS = {"agent", "planning", "reasoning", "retrieval", "memory", "tool", "guard", "delegation", "llm", "coordinator", "router"}
BANNED = {"injected", "injection", "origin", "clean_value", "faulty_value", "corrupt", "stale", "mismatch", "faulty"}
NORMALIZED_KEYS = {
    "event_id", "step_index", "logical_time", "source_pointer", "actor_id",
    "actor_role", "display_name", "component_type", "event_type",
    "parent_event_ids", "dependency_event_ids", "workflow.stage", "workflow.position",
}


def values(value: Any, key: str = "") -> list[str]:
    if key in NORMALIZED_KEYS:
        return []
    if isinstance(value, dict):
        return sum((values(child, child_key) for child_key, child in value.items()), [])
    if isinstance(value, list):
        return sum((values(child) for child in value), [])
    if value is None:
        return []
    return [" ".join(token for token in re.findall(r"[a-zA-Z0-9_]+", str(value).lower()) if token not in COMPONENT_WORDS)]


def text_for(row: dict, mode: str) -> str:
    events = row["events"]
    if mode == "terminal":
        events = events[-1:]
    elif mode == "source":
        origin = row["labels"]["origin_event_id"]
        # This is a *content* shortcut audit, not an oracle component-kind
        # classifier.  Retain only normalized workflow facts and discard
        # tool/retrieval/memory payload shapes that identify the span type.
        event = next(event for event in events if event["event_id"] == origin)
        return " ".join(values(structured(event)))
    return " ".join(sum((values(event) for event in events), []))


def logo(rows: list[dict], mode: str, analyzer: str) -> float | None:
    """Leave-one-domain-out lexical origin classifier with identifiers removed."""
    scores: list[bool] = []
    for domain in sorted({row["metadata"]["domain"] for row in rows}):
        train = [row for row in rows if row["metadata"]["domain"] != domain]
        test = [row for row in rows if row["metadata"]["domain"] == domain]
        train_text, test_text = [text_for(row, mode) for row in train], [text_for(row, mode) for row in test]
        if not any(train_text) or not any(test_text):
            return None
        vectorizer = TfidfVectorizer(analyzer=analyzer, ngram_range=(3, 5) if analyzer == "char" else (1, 2), min_df=1)
        model = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=13)
        model.fit(vectorizer.fit_transform(train_text), [row["labels"]["origin_component"] for row in train])
        scores.extend(predicted == row["labels"]["origin_component"] for predicted, row in zip(model.predict(vectorizer.transform(test_text)), test))
    return sum(scores) / len(scores)


def event_by_id(row: dict, event_id: str) -> dict:
    return next(event for event in row["events"] if event["event_id"] == event_id)


def structured(event: dict) -> dict:
    value = event["output"].get("structured")
    return value if isinstance(value, dict) else {}


def expected_target(row: dict) -> str | None:
    for event in reversed(row["events"]):
        value = structured(event).get("workflow.expected_target")
        if value:
            return str(value)
    return None


def first_value_deviation(row: dict) -> str | None:
    expected = expected_target(row)
    if not expected:
        return None
    for event in row["events"]:
        target = structured(event).get("workflow.target_id")
        if target is not None and str(target) != expected:
            return event["event_id"]
    return None


def deterministic_witness_origin(row: dict) -> str | None:
    """Recover the latent origin from an explicit registry and consumed binding."""
    expected = expected_target(row)
    registry = next((structured(event).get("workflow.reference_map") for event in row["events"] if structured(event).get("workflow.reference_map")), None)
    if not expected or not isinstance(registry, str):
        return None
    mappings = {}
    for clause in registry.split(";"):
        if "->" in clause:
            reference, target = clause.split("->", 1)
            mappings[reference] = target
    for event in row["events"]:
        reference = structured(event).get("workflow.reference")
        if reference in mappings and mappings[reference] != expected:
            return event["event_id"]
    return None


def matched_groups(rows: list[dict]) -> dict[str, Any]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        group = row["metadata"].get("matched_group_id")
        if group:
            groups[group].append(row)
    valid = 0
    failures: list[str] = []
    for group, members in sorted(groups.items()):
        origins = {member["labels"]["origin_component"] for member in members}
        task_keys = {(member["task_id"], member["metadata"].get("terminal_symptom"), member["metadata"].get("delayed_operator")) for member in members}
        first_types = {event_by_id(member, member["labels"]["first_visible_deviation_event_id"])["event_type"] for member in members}
        if len(members) == 2 and len(origins) == 2 and len(task_keys) == 1 and len(first_types) == 1:
            valid += 1
        else:
            failures.append(group)
    return {"groups": len(groups), "valid_groups": valid, "valid_fraction": valid / len(groups) if groups else 0.0, "invalid_group_ids": failures}


def r3_report(rows: list[dict], faults: list[dict]) -> dict[str, Any]:
    first_value = [first_value_deviation(row) for row in faults]
    origin = [row["labels"]["origin_event_id"] for row in faults]
    first_visible = [row["labels"]["first_visible_deviation_event_id"] for row in faults]
    distances = []
    for row, origin_id, visible_id in zip(faults, origin, first_visible):
        positions = {event["event_id"]: event["step_index"] for event in row["events"]}
        distances.append(positions[visible_id] - positions[origin_id])
    witness = [deterministic_witness_origin(row) == row["labels"]["origin_event_id"] for row in faults]
    group = matched_groups(faults)
    return {
        "first_value_deviation_matches_label": sum(value == label for value, label in zip(first_value, first_visible)) / len(faults),
        "first_value_deviation_origin_top1": sum(value == label for value, label in zip(first_value, origin)) / len(faults),
        "origin_differs_from_first_visible_fraction": sum(left != right for left, right in zip(origin, first_visible)) / len(faults),
        "origin_to_first_visible_distance": {"min": min(distances), "median": sorted(distances)[len(distances) // 2], "at_least_2_fraction": sum(distance >= 2 for distance in distances) / len(distances)},
        "deterministic_graph_witness_recovery": sum(witness) / len(witness),
        "matched_counterfactuals": group,
        "gates": {
            "first_value_deviation_origin_top1_lte_0_40": sum(value == label for value, label in zip(first_value, origin)) / len(faults) <= 0.40,
            "origin_differs_from_first_visible_gte_0_70": sum(left != right for left, right in zip(origin, first_visible)) / len(faults) >= 0.70,
            "origin_distance_gte_2_gte_0_50": sum(distance >= 2 for distance in distances) / len(distances) >= 0.50,
            "graph_witness_recovery_eq_1_00": sum(witness) == len(witness),
            "matched_groups_gte_0_50": group["valid_fraction"] >= 0.50,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(path.read_text()) for path in sorted(args.input.glob("*.json"))]
    faults = [row for row in rows if row["labels"]["is_fault"]]
    if not rows or not faults:
        raise SystemExit("input must contain canonical clean and fault traces")
    visible = json.dumps([{"events": row["events"]} for row in rows]).lower()
    components = [row["labels"]["origin_component"] for row in faults]
    majority = Counter(components).most_common(1)[0][0]
    lexical = {f"{mode}_{analyzer}": logo(faults, mode, analyzer) for mode in ("all", "terminal", "source") for analyzer in ("word", "char")}
    report: dict[str, Any] = {
        "traces": len(rows), "faults": len(faults), "banned_visible_tokens": sorted(token for token in BANNED if token in visible),
        "random_visible_event_expected": sum(1 / len(row["events"]) for row in faults) / len(faults),
        "majority_component": majority, "majority_component_accuracy": components.count(majority) / len(components),
        "lexical_component_accuracy_leave_one_domain_out": lexical,
    }
    if all(row["labels"].get("first_visible_deviation_event_id") for row in faults):
        report["r3"] = r3_report(rows, faults)
        report["r3"]["gates"]["normalized_source_lexical_lte_0_25"] = max(lexical["source_word"], lexical["source_char"]) <= 0.25
        report["r3"]["gates"]["full_and_terminal_near_random"] = max(lexical["all_word"], lexical["all_char"], lexical["terminal_word"], lexical["terminal_char"]) <= 0.25
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
