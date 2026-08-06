"""Map predicted events to the preregistered causal-stage vocabulary."""

from __future__ import annotations


def causal_stage(job: dict, event_id: str | None) -> str:
    if event_id is None:
        return "abstain"
    positions = job["gold_causal_positions"]
    for stage in ("origin", "activation", "first_visible_deviation", "symptom", "terminal"):
        if event_id == positions.get(stage):
            return stage
    return "other"
