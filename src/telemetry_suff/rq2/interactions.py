"""Preregistered factor contrasts computed from per-mask metric rows."""

from __future__ import annotations

from .masks import mask_for


def _score_contrasts(metrics: list[dict], score: str) -> dict:
    values = {
        row["mask_id"]: (
            row["causal_stage_attribution"][score.removesuffix("_attribution_rate")]
            if score.endswith("_attribution_rate") else row[score]
        )
        for row in metrics
    }
    full = mask_for(set("IDPRSVT")).mask_id
    necessity = {
        factor: values.get(full, 0.0) - values.get(mask_for(set("IDPRSVT") - {factor}).mask_id, 0.0)
        for factor in "IDPRSVT"
    }
    dpv = values.get(mask_for({"D", "P", "V"}).mask_id, 0.0)
    idpv = values.get(mask_for({"I", "D", "P", "V"}).mask_id, 0.0)
    primary = {
        "I+D+P+V_minus_D+P+V": idpv - dpv,
        "I+D+P+V_minus_S+V+T": idpv - values.get(mask_for({"S", "V", "T"}).mask_id, 0.0),
        "Full_minus_S+V+T": values.get(full, 0.0) - values.get(mask_for({"S", "V", "T"}).mask_id, 0.0),
    }
    return {"leave_one_out_drop": necessity, "primary_mechanism_contrasts": primary}


def contrasts(metrics: list[dict], score: str | None = None) -> dict:
    if score:
        return {"score": score, **_score_contrasts(metrics, score)}
    scores = ("detection_f1", "component_accuracy", "origin_step_top1", "origin_attribution_rate", "symptom_attribution_rate")
    output = {name: _score_contrasts(metrics, name) for name in scores}
    # The symptom requirement is expressed as an increase after ablation, the
    # reverse sign of the generic Full-minus-ablated necessity contrast.
    output["symptom_attribution_rate"]["symptom_increase_after_ablation"] = {
        factor: -drop for factor, drop in output["symptom_attribution_rate"]["leave_one_out_drop"].items()
    }
    return output
