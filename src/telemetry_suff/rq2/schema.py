"""Small schemas shared by RQ2's offline pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RenderedTrace:
    trace_id: str
    mask_id: str
    content: str
    render_hash: str
    candidate_event_ids: tuple[str, ...]
    candidate_components: tuple[str, ...]
    unknown_fields: tuple[str, ...]
    origin_witness_candidate_ids: tuple[str, ...] = ()

    def parsed(self) -> dict[str, Any]:
        import json
        return json.loads(self.content)
