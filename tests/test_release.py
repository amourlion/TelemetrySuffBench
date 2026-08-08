import hashlib
import json
from pathlib import Path

from telemetry_suff.rq2.experiment_design import rq2_masks, validate_frozen_splits
from telemetry_suff.rq2.offline_analysis import load_traces


ROOT = Path(__file__).resolve().parents[1]


def test_dataset_counts() -> None:
    main = load_traces(ROOT / "data/canonical/agenttelemetry_component_extension_v1_r3")
    holdout_dir = ROOT / "data/canonical/agenttelemetry_component_extension_v1_r3_blind_s20260730"
    holdout = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(holdout_dir.glob("*.json"))]
    assert (len(main), sum(row["labels"]["is_fault"] for row in main)) == (312, 216)
    assert (len(holdout), sum(row["labels"]["is_fault"] for row in holdout)) == (216, 144)


def test_rq2_panel_and_splits() -> None:
    assert len(rq2_masks()) == 11
    assert len({mask.mask_id for mask in rq2_masks()}) == 11
    result = validate_frozen_splits(ROOT)
    assert result["confirmation"]["traces"] == 216
    assert result["mask_count"] == 11


def test_release_manifest_and_dataset_hashes() -> None:
    manifest = json.loads((ROOT / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    checksum_path = ROOT / manifest["dataset_checksum_manifest"]
    checksum_bytes = checksum_path.read_bytes()
    assert hashlib.sha256(checksum_bytes).hexdigest() == manifest["dataset_checksum_manifest_sha256"]
    entries = [line.split(maxsplit=1) for line in checksum_bytes.decode().splitlines() if line]
    assert len(entries) == manifest["dataset_checksum_entries"] == 544
    for expected, relative in entries:
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
