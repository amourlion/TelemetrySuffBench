#!/usr/bin/env python3
"""Build the fixed 96-trace, component-balanced R3 smoke split."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(args.input.glob("*.json"))]
    selected: list[dict] = []
    for row in rows:
        if not row["labels"]["is_fault"]:
            # 3 domains x 4 topologies x 2 variants = 24 clean controls.
            if row["metadata"]["task_variant"] < 2:
                selected.append(row)
            continue
        group_index = int(row["metadata"]["matched_group_id"].rsplit("_", 1)[1])
        cycle, edge = divmod(group_index, 9)
        selected_edges = {(3 * cycle + offset) % 9 for offset in range(3)}
        if edge in selected_edges:
            selected.append(row)
    faults = [row for row in selected if row["labels"]["is_fault"]]
    clean = [row for row in selected if not row["labels"]["is_fault"]]
    component_counts = Counter(row["labels"]["origin_component"] for row in faults)
    if len(selected) != 96 or len(faults) != 72 or len(clean) != 24 or set(component_counts.values()) != {8} or len(component_counts) != 9:
        raise SystemExit(f"invalid smoke selection: total={len(selected)} faults={len(faults)} clean={len(clean)} components={dict(component_counts)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(row["trace_id"] for row in selected) + "\n", encoding="utf-8")
    manifest = {
        "dataset": "agenttelemetry_component_extension_v1_r3",
        "selection": "paired-cycle component-balanced smoke",
        "traces": len(selected), "faults": len(faults), "clean": len(clean),
        "component_counts": dict(sorted(component_counts.items())),
        "views": 6, "queue_tasks": len(selected) * 6,
    }
    args.output.with_suffix(".json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
