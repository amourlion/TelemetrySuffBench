"""Exact six-signal Shapley attribution over all 64 coalitions."""
from __future__ import annotations
from math import factorial
from telemetry_suff.views.transform import SIGNALS

def exact_shapley(scores: dict[int, float]) -> dict[str, float]:
    if set(scores) != set(range(64)):
        raise ValueError("scores must include exactly masks 0..63")
    n = len(SIGNALS); result: dict[str, float] = {}
    for index, signal in enumerate(SIGNALS):
        bit = 1 << index; value = 0.0
        for coalition in range(64):
            if coalition & bit: continue
            size = coalition.bit_count()
            weight = factorial(size) * factorial(n-size-1) / factorial(n)
            value += weight * (scores[coalition | bit] - scores[coalition])
        result[signal] = value
    return result

def minimal_sufficient_sets(scores: dict[int, float], epsilon: float = 0.05) -> list[int]:
    target = scores[63] - epsilon
    valid = [mask for mask, score in scores.items() if score >= target]
    smallest = min(mask.bit_count() for mask in valid)
    return [mask for mask in valid if mask.bit_count() == smallest]
