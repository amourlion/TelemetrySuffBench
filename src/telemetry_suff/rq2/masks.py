"""Stable enumeration and selection of all 2^7 factor masks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path

from .factors import FACTOR_ORDER, FactorManifest, load_manifest


@dataclass(frozen=True)
class Mask:
    mask_id: str
    enabled_factors: tuple[str, ...]
    disabled_factors: tuple[str, ...]
    factor_count: int
    renderer_version: str
    manifest_version: str
    stable_hash: str

    def to_dict(self) -> dict:
        value = asdict(self)
        value["enabled_factors"] = list(self.enabled_factors)
        value["disabled_factors"] = list(self.disabled_factors)
        return value


def mask_from_bits(bits: str, manifest: FactorManifest | None = None) -> Mask:
    manifest = manifest or load_manifest()
    if len(bits) != 7 or set(bits) - {"0", "1"}:
        raise ValueError("mask bits must be a seven-character binary string")
    enabled = tuple(key for key, bit in zip(FACTOR_ORDER, bits) if bit == "1")
    disabled = tuple(key for key in FACTOR_ORDER if key not in enabled)
    payload = f"{manifest.version}|{manifest.renderer_version}|{''.join(bits)}"
    return Mask(
        mask_id=f"mask_{bits}", enabled_factors=enabled, disabled_factors=disabled,
        factor_count=len(enabled), renderer_version=manifest.renderer_version,
        manifest_version=manifest.version, stable_hash=hashlib.sha256(payload.encode()).hexdigest(),
    )


def mask_for(factors: set[str] | tuple[str, ...] | list[str], manifest: FactorManifest | None = None) -> Mask:
    enabled = set(factors)
    if enabled - set(FACTOR_ORDER):
        raise ValueError(f"unknown factors: {enabled - set(FACTOR_ORDER)}")
    return mask_from_bits("".join("1" if key in enabled else "0" for key in FACTOR_ORDER), manifest)


def all_masks(manifest: FactorManifest | None = None) -> list[Mask]:
    manifest = manifest or load_manifest()
    return [mask_from_bits(f"{value:07b}", manifest) for value in range(128)]


def write_all_masks(path: Path, manifest: FactorManifest | None = None) -> list[Mask]:
    masks = all_masks(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([mask.to_dict() for mask in masks], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return masks


def strict_subsets(mask: Mask, manifest: FactorManifest | None = None) -> list[Mask]:
    return [mask_for(set(combo), manifest) for size in range(mask.factor_count) for combo in combinations(mask.enabled_factors, size)]
