"""Preregistered selection of at most ten confirmation masks."""

from __future__ import annotations

import json
from pathlib import Path

from .masks import Mask, all_masks, mask_for


def select_confirmation_masks(discovery_metrics: list[dict], surprise_mask_id: str | None = None) -> tuple[list[str], dict]:
    by_id = {row["mask_id"]: row for row in discovery_metrics}
    full = mask_for(set("IDPRSVT")).mask_id
    fixed = [full, mask_for(set()).mask_id, mask_for({"D", "P", "R"}).mask_id, mask_for({"S", "V", "T"}).mask_id]
    full_score = by_id[full]["origin_step_top1"]
    loo = [mask_for(set("IDPRSVT") - {factor}).mask_id for factor in "IDPRSVT"]
    loo_rank = sorted(
        loo,
        key=lambda mid: (
            -(full_score - by_id[mid]["origin_step_top1"]),
            -by_id[mid]["component_accuracy"],
            mid,
        ),
    )
    def performance_key(mid: str) -> tuple:
        mask = next(mask for mask in all_masks() if mask.mask_id == mid)
        row = by_id[mid]
        return (-row["origin_step_top1"], -row["component_accuracy"], mask.factor_count, mid)
    strict = [mid for mid in by_id if mid != full and next(mask.factor_count for mask in all_masks() if mask.mask_id == mid) < 7]
    two_factor = [mid for mid in by_id if next(mask.factor_count for mask in all_masks() if mask.mask_id == mid) == 2]
    selected = fixed + loo_rank[:3] + [min(strict, key=performance_key), min(two_factor, key=performance_key)]
    if surprise_mask_id is None:
        surprise_mask_id = min((mid for mid in by_id if mid not in selected), key=performance_key)
    selected.append(surprise_mask_id)
    deduped = list(dict.fromkeys(selected))
    for mid in sorted(by_id, key=performance_key):
        if len(deduped) >= 10:
            break
        if mid not in deduped:
            deduped.append(mid)
    audit = {
        "selection_status": "mock_only_pending_real_discovery_predictions",
        "selected_mask_ids": deduped[:10],
        "full_origin_step_top1": full_score,
        "leave_one_out_drops": {mid: full_score - by_id[mid]["origin_step_top1"] for mid in loo},
        "tie_break": ["origin_step_top1", "component_accuracy", "fewer_factors", "mask_id_lexicographic"],
    }
    return deduped[:10], audit


def write_selection(root: Path, selected: list[str], audit: dict, *, status: str = "mock_fixture_only") -> None:
    manifest_path = root / "data/rq2/manifests/rq2_confirmation_selected_10_masks.json"
    audit_path = root / "results/metrics/rq2_confirmation_selection_audit.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({"status": status, "mask_ids": selected}, indent=2, sort_keys=True) + "\n")
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
