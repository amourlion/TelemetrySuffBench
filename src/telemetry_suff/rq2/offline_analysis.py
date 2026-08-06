"""Complete 312 x 128 offline enumeration and theoretical set discovery."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .equivalence import classify_equivalence, mask_render_equivalence
from .factors import FACTOR_ORDER, load_manifest
from .masks import Mask, all_masks, mask_for, strict_subsets
from .renderer import render_trace
from .witness import analyze_witness

DATASET_DIR = Path("data/canonical/agenttelemetry_component_extension_v1_r3")


def load_traces(directory: Path = DATASET_DIR) -> list[dict]:
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))]
    if len(rows) != 312:
        raise ValueError(f"frozen R3 source must contain 312 traces, found {len(rows)}")
    return rows


def _write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    names = fieldnames or list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, sort_keys=True) if isinstance(value, (list, dict)) else value for key, value in row.items()})


def _minimal_and_maximal(summary: list[dict], criterion: str, masks_by_id: dict[str, Mask]) -> tuple[list[str], list[str]]:
    sufficient = {row["mask_id"] for row in summary if row[criterion] == 1.0}
    minimal = []
    maximal = []
    for mask_id, mask in masks_by_id.items():
        if mask_id in sufficient:
            if not any(child.mask_id in sufficient for child in strict_subsets(mask)):
                minimal.append(mask_id)
        else:
            missing = set(FACTOR_ORDER) - set(mask.enabled_factors)
            if missing and all(mask_for(set(mask.enabled_factors) | {factor}).mask_id in sufficient for factor in missing):
                maximal.append(mask_id)
    return sorted(minimal), sorted(maximal)


def _pareto(rows: list[dict]) -> list[dict]:
    fields_min = ("factor_count", "average_rendered_characters")
    fields_max = ("witness_recoverability", "gold_answerable_rate", "terminal_detection_evidence_rate")
    frontier = []
    for row in rows:
        dominated = False
        for other in rows:
            if other is row:
                continue
            no_worse = all(other[key] <= row[key] for key in fields_min) and all(other[key] >= row[key] for key in fields_max)
            strictly = any(other[key] < row[key] for key in fields_min) or any(other[key] > row[key] for key in fields_max)
            if no_worse and strictly:
                dominated = True
                break
        if not dominated:
            frontier.append(row)
    return sorted(frontier, key=lambda row: (row["factor_count"], row["mask_id"]))


def run_offline_enumeration(root: Path = Path(".")) -> dict:
    manifest = load_manifest(root / "config/rq2_signal_factors_v1.yaml")
    traces = load_traces(root / DATASET_DIR)
    masks = all_masks(manifest)
    rendered = [render_trace(trace, mask, manifest) for mask in masks for trace in traces]
    witnesses = [
        analyze_witness(trace, mask, rendered_item)
        for mask in masks
        for trace, rendered_item in zip(traces, [item for item in rendered if item.mask_id == mask.mask_id])
    ]
    equivalence = classify_equivalence(traces, rendered)
    witness_lookup = {(row["trace_id"], row["mask_id"]): row for row in witnesses}
    eq_lookup = {(row["trace_id"], row["mask_id"]): row for row in equivalence}
    trace_lookup = {trace["trace_id"]: trace for trace in traces}
    summary: list[dict] = []
    for mask in masks:
        items = [item for item in rendered if item.mask_id == mask.mask_id]
        faults = [item for item in items if trace_lookup[item.trace_id]["labels"]["is_fault"]]
        clean = [item for item in items if not trace_lookup[item.trace_id]["labels"]["is_fault"]]
        summary.append({
            "mask_id": mask.mask_id,
            "enabled_factors": list(mask.enabled_factors),
            "factor_count": mask.factor_count,
            "witness_recoverability": sum(witness_lookup[(item.trace_id, mask.mask_id)]["witness_recoverable"] for item in faults) / len(faults),
            "gold_answerable_rate": sum(eq_lookup[(item.trace_id, mask.mask_id)]["gold_answerable"] for item in faults) / len(faults),
            "terminal_detection_evidence_rate": 1.0 if "T" in mask.enabled_factors else 0.0,
            "detection_evidence_visible": "T" in mask.enabled_factors,
            "average_rendered_characters": sum(len(item.content) for item in items) / len(items),
            "average_rendered_characters_fault": sum(len(item.content) for item in faults) / len(faults),
            "average_rendered_characters_clean": sum(len(item.content) for item in clean) / len(clean),
            "unknown_field_count": sum(len(item.unknown_fields) for item in items),
        })
    masks_by_id = {mask.mask_id: mask for mask in masks}
    minimal_witness, maximal_witness = _minimal_and_maximal(summary, "witness_recoverability", masks_by_id)
    minimal_answerable, maximal_answerable = _minimal_and_maximal(summary, "gold_answerable_rate", masks_by_id)
    theoretical = {
        "definition": "offline instrumentation and observational answerability; not model accuracy",
        "minimal_witness_recoverability_100pct": minimal_witness,
        "maximal_witness_insufficient": maximal_witness,
        "minimal_gold_answerable_100pct": minimal_answerable,
        "maximal_gold_answerable_insufficient": maximal_answerable,
        "stratified_minimal_sets": _stratified_minimal(traces, equivalence, witnesses, masks),
    }
    fault_ids = {trace["trace_id"] for trace in traces if trace["labels"]["is_fault"]}
    clean_ids = set(trace_lookup) - fault_ids
    result = {
        "dataset": "agenttelemetry_component_extension_v1_r3",
        "trace_count": len(traces), "mask_count": len(masks),
        "render_count": len(rendered), "api_requests": 0,
        "summary": summary,
        "witness_records": witnesses,
        "equivalence_records": equivalence,
        "render_equivalence": {
            "all": mask_render_equivalence(rendered),
            "fault": mask_render_equivalence(rendered, fault_ids),
            "clean": mask_render_equivalence(rendered, clean_ids),
        },
        "theoretical": theoretical,
    }
    metrics = root / "results/metrics"
    tables = root / "results/tables"
    metrics.mkdir(parents=True, exist_ok=True)
    (metrics / "rq2_offline_128_mask_analysis.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (metrics / "rq2_theoretical_minimal_sets.json").write_text(json.dumps(theoretical, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_csv(tables / "rq2_offline_mask_summary.csv", summary)
    _write_csv(tables / "rq2_offline_equivalence_classes.csv", equivalence)
    _write_csv(tables / "rq2_offline_answerability_by_mask.csv", [
        {"mask_id": row["mask_id"], "gold_answerable_rate": row["gold_answerable_rate"],
         "witness_recoverability": row["witness_recoverability"],
         "detection_evidence_visible": row["detection_evidence_visible"]}
        for row in summary
    ])
    theory_rows = [
        {"criterion": criterion, "set_type": set_type, "mask_id": mask_id}
        for criterion, set_type, values in (
            ("witness_recoverability", "minimal_sufficient", minimal_witness),
            ("witness_recoverability", "maximal_insufficient", maximal_witness),
            ("gold_answerable", "minimal_sufficient", minimal_answerable),
            ("gold_answerable", "maximal_insufficient", maximal_answerable),
        ) for mask_id in values
    ]
    _write_csv(tables / "rq2_theoretical_minimal_sets.csv", theory_rows)
    _write_csv(tables / "rq2_theoretical_pareto_frontier.csv", _pareto(summary))
    return result


def _stratified_minimal(traces: list[dict], equivalence: list[dict], witnesses: list[dict], masks: list[Mask]) -> dict:
    w_lookup = {(row["trace_id"], row["mask_id"]): row for row in witnesses}
    e_lookup = {(row["trace_id"], row["mask_id"]): row for row in equivalence}
    dimensions = {
        "operator": lambda trace: trace["metadata"].get("delayed_operator"),
        "domain": lambda trace: trace["metadata"].get("domain"),
        "origin_component": lambda trace: trace["labels"].get("origin_component"),
    }
    output: dict[str, dict[str, dict[str, list[str]]]] = {
        "witness_recoverability": {}, "gold_answerable": {},
    }
    criteria = {
        "witness_recoverability": lambda trace_id, mask_id: w_lookup[(trace_id, mask_id)]["witness_recoverable"],
        "gold_answerable": lambda trace_id, mask_id: e_lookup[(trace_id, mask_id)]["gold_answerable"],
    }
    for criterion, predicate in criteria.items():
        for dimension, accessor in dimensions.items():
            values = sorted({accessor(trace) for trace in traces if trace["labels"]["is_fault"]})
            output[criterion][dimension] = {}
            for value in values:
                ids = [trace["trace_id"] for trace in traces if trace["labels"]["is_fault"] and accessor(trace) == value]
                sufficient = {
                    mask.mask_id for mask in masks
                    if ids and all(predicate(trace_id, mask.mask_id) for trace_id in ids)
                }
                output[criterion][dimension][str(value)] = sorted(
                    mask.mask_id for mask in masks if mask.mask_id in sufficient
                    and not any(child.mask_id in sufficient for child in strict_subsets(mask))
                )
    return output
