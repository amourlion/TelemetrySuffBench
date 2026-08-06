"""Matched-group cluster bootstrap preserving all traces and masks."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Callable


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot take percentile of empty values")
    index = (len(ordered) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def cluster_bootstrap(
    rows: list[dict],
    statistic: Callable[[list[dict]], float],
    *,
    group_key: str = "matched_group_id",
    repetitions: int = 10_000,
    seed: int = 20260728,
) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[str(row[group_key])].append(row)
    keys = sorted(groups)
    rng = random.Random(seed)
    samples = []
    for _ in range(repetitions):
        selected = [rng.choice(keys) for _ in keys]
        sample = [dict(row, _bootstrap_cluster_index=index) for index, key in enumerate(selected) for row in groups[key]]
        samples.append(statistic(sample))
    return {
        "estimate": statistic(rows), "repetitions": repetitions, "seed": seed,
        "percentile_95_ci": [percentile(samples, 0.025), percentile(samples, 0.975)],
    }


def paired_mask_difference(
    rows: list[dict],
    score: Callable[[list[dict]], float],
    mask_a: str,
    mask_b: str,
    **kwargs,
) -> dict:
    def statistic(sample: list[dict]) -> float:
        return score([row for row in sample if row["mask_id"] == mask_a]) - score([row for row in sample if row["mask_id"] == mask_b])
    return cluster_bootstrap(rows, statistic, **kwargs)
