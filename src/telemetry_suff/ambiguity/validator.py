"""Validation primitives for exact and structural observational ambiguity."""

from __future__ import annotations

from dataclasses import dataclass

from telemetry_suff.views import fingerprint, structural_fingerprint


@dataclass(frozen=True)
class AmbiguityItem:
    origin_label: str
    view: dict


def candidate_origins(items: list[AmbiguityItem], level: str = "exact") -> dict[str, set[str]]:
    hasher = fingerprint if level == "exact" else structural_fingerprint
    groups: dict[str, set[str]] = {}
    for item in items:
        groups.setdefault(hasher(item.view), set()).add(item.origin_label)
    return groups


def answerability(items: list[AmbiguityItem], level: str = "exact") -> dict[str, bool]:
    return {key: len(origins) == 1 for key, origins in candidate_origins(items, level).items()}


def assert_collision(left: AmbiguityItem, right: AmbiguityItem, level: str = "exact") -> None:
    hasher = fingerprint if level == "exact" else structural_fingerprint
    if left.origin_label == right.origin_label:
        raise ValueError("ambiguity collision requires distinct origin labels")
    if hasher(left.view) != hasher(right.view):
        raise ValueError(f"{level} collision validation failed")
