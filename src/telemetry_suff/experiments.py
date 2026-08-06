"""Prepare paired views as portable JSONL inference jobs."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from telemetry_suff.schema import CanonicalTrace
from telemetry_suff.views import build_coarse_view, build_mask_view, fingerprint

def prepare(input_dir: Path, output: Path, families: list[str], masks: list[int] | None = None, include_trace_ids: set[str] | None = None) -> int:
    output.parent.mkdir(parents=True, exist_ok=True); count = 0
    with output.open("w", encoding="utf-8") as sink:
        for source in sorted(input_dir.glob("*.json")):
            trace = CanonicalTrace.model_validate_json(source.read_text(encoding="utf-8"))
            if include_trace_ids is not None and trace.trace_id not in include_trace_ids:
                continue
            views = [(family, build_coarse_view(trace, family)) for family in families]
            if masks:
                views.extend((f"mask_{mask:02d}", build_mask_view(trace, mask)) for mask in masks)
            for view_id, view in views:
                view["observed_fingerprint"] = fingerprint(view)
                task_id = hashlib.sha256(f"{trace.trace_id}:{view_id}:{view['observed_fingerprint']}".encode()).hexdigest()
                sink.write(json.dumps({"task_id": task_id, "trace_id": trace.trace_id, "view_id": view_id, "view": view, "labels": trace.labels.model_dump(), "source_metadata": trace.metadata}, ensure_ascii=False) + "\n"); count += 1
    return count
