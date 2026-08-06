# TelemetrySuffBench Artifact

Public repository: <https://github.com/amourlion/TelemetrySuffBench>

This directory is a publication-ready staging area for the TelemetrySuffBench dataset and the offline code needed to reconstruct the paper's RQ1, RQ2, and RQ3 model inputs and score normalized predictions. It intentionally contains no credentials, endpoints, request histories, response transcripts, or deployment-specific adapters.

## Contents

- `data/canonical/`: the 312-trace main dataset and the 216-trace seeded holdout.
- `data/splits/`: the fixed RQ1/RQ2 and RQ3 splits.
- `data/rq2/` and `data/rq3/`: mask and logical-job manifests.
- `src/telemetry_suff/`: canonical schemas, deterministic renderers, validation, metrics, and bootstrap code.
- `scripts/`: model-input builders, scorers, and dataset audits.
- `DATASET_CARD.md`: construction, labels, scope, and known constraints.

## Install

Python 3.11 or later is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
```

## Build model inputs

Run these commands from the repository root:

```bash
python scripts/build_rq1_jobs.py
python scripts/build_rq2_jobs.py
python scripts/build_rq3_requests.py
```

Generated model-visible requests are written to `outputs/requests/`. Gold-bearing manifests used only for scoring are written to `outputs/private/`. The fixed RQ2 panel contains Full, seven leave-one-factor-out masks, and the I+D+P+V, D+P+V, and S+V+T subsets.

## Bring your own model runner

The release does not prescribe an inference client. For each JSONL row in `outputs/requests/`, send only the supplied `system` and `user` fields, or the supplied `model_visible_payload`, to the model under test. Save one JSON object per line with the same `request_id` and a parsed `prediction` object. The scorers map `request_id` back to the private logical job. Keep model identity, decoding settings, and run metadata in a separate experiment manifest.

RQ1 predictions use `is_fault`, `fault_type`, `origin_component`, `origin_event_id`, `answerability`, and `confidence`. RQ2 predictions use `fault_present`, `fault_type`, `answerability`, `origin_component`, and `origin_event_id`. RQ3 predictions use `answerability`, `origin_component`, and `origin_event_id`. Invalid or incomplete objects remain in the denominator and receive no correctness credit.

## Score normalized predictions

```bash
python scripts/score_rq1.py --predictions PATH.jsonl
python scripts/score_rq2.py --predictions PATH.jsonl
python scripts/score_rq3.py --jobs data/rq3/manifests/rq3_confirmation_logical_jobs.jsonl --predictions PATH.jsonl
```

The scorers do not make network calls. Before the archival release, select a license, freeze the final hashes, and complete `RELEASE_CHECKLIST.md`.
