"""Localization metrics independent of a particular model provider."""

from __future__ import annotations


def accuracy(predicted: list[str | None], actual: list[str | None]) -> float:
    if len(predicted) != len(actual) or not actual:
        raise ValueError("predictions and nonempty labels must have equal length")
    return sum(left == right for left, right in zip(predicted, actual)) / len(actual)


def localization_beyond_detection(full_detection: float, view_detection: float, full_localization: float, view_localization: float) -> float:
    if full_detection == 0 or full_localization == 0:
        raise ValueError("full scores must be nonzero")
    detection_drop = (full_detection - view_detection) / full_detection
    localization_drop = (full_localization - view_localization) / full_localization
    return localization_drop - detection_drop
