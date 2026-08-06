"""Manifest-driven semantic telemetry factors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

FACTOR_ORDER = ("I", "D", "P", "R", "S", "V", "T")
DEFAULT_MANIFEST = Path("config/rq2_signal_factors_v1.yaml")


@dataclass(frozen=True)
class Factor:
    key: str
    description: str
    fields: tuple[str, ...]
    deletion: str


@dataclass(frozen=True)
class FactorManifest:
    version: str
    renderer_version: str
    bit_order: tuple[str, ...]
    redaction: str
    always_visible: tuple[str, ...]
    factors: dict[str, Factor]
    shared_fields: tuple[str, ...]
    private_never_visible: tuple[str, ...]
    ignored_known_fields: tuple[str, ...]

    @property
    def field_to_factor(self) -> dict[str, str]:
        return {field: key for key, factor in self.factors.items() for field in factor.fields}

    @property
    def known_paths(self) -> set[str]:
        return set(self.always_visible) | set(self.field_to_factor) | set(self.ignored_known_fields)

    def validate(self) -> None:
        if self.bit_order != FACTOR_ORDER:
            raise ValueError(f"factor bit order must be {FACTOR_ORDER}")
        if set(self.factors) != set(FACTOR_ORDER):
            raise ValueError("manifest must define exactly I,D,P,R,S,V,T")
        owners: dict[str, list[str]] = {}
        for key, factor in self.factors.items():
            if factor.deletion not in {"redact", "null", "delete"}:
                raise ValueError(f"unsupported deletion strategy for {key}")
            for field in factor.fields:
                owners.setdefault(field, []).append(key)
        duplicates = {field: keys for field, keys in owners.items() if len(keys) > 1 and field not in self.shared_fields}
        if duplicates:
            raise ValueError(f"fields have multiple owners: {duplicates}")
        forbidden = ("label", "injection", "origin_", "causal_stage", "gold_")
        leaked = [field for field in owners if any(token in field.lower() for token in forbidden)]
        if leaked:
            raise ValueError(f"private fields assigned to factors: {leaked}")


def load_manifest(path: Path | str = DEFAULT_MANIFEST) -> FactorManifest:
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    manifest = FactorManifest(
        version=raw["version"],
        renderer_version=raw["renderer_version"],
        bit_order=tuple(raw["bit_order"]),
        redaction=raw.get("redaction", "<REDACTED>"),
        always_visible=tuple(raw["always_visible"]),
        factors={
            key: Factor(key, value["description"], tuple(value["fields"]), value.get("deletion", "redact"))
            for key, value in raw["factors"].items()
        },
        shared_fields=tuple(raw.get("shared_fields", [])),
        private_never_visible=tuple(raw.get("private_never_visible", [])),
        ignored_known_fields=tuple(raw.get("ignored_known_fields", [])),
    )
    manifest.validate()
    return manifest
