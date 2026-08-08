# TelemetrySuffBench

Public repository: <https://github.com/amourlion/TelemetrySuffBench>

This is the versioned research artifact for *TelemetrySuffBench: Is Agent Telemetry Sufficient for Failure-Origin Diagnosis?* It contains the released benchmark data and the offline code needed to reconstruct the paper's RQ1, RQ2, and RQ3 model inputs and score normalized predictions. Release `v1.0.0` contains no credentials, inference endpoints, request histories, model-response transcripts, or deployment-specific adapters.

## Release status

Release `v1.0.0` freezes the paper dataset and protocols. It contains 312 main traces and 216 seeded holdout traces. `DATASET_SHA256SUMS.txt` records SHA-256 hashes for all 544 released data, split, and protocol files. `RELEASE_MANIFEST.json` records the released counts and checksum-manifest digest.

## Contents

- `data/canonical/`: the 312-trace main dataset and the 216-trace seeded holdout.
- `data/splits/`: the fixed RQ1/RQ2 and RQ3 splits.
- `data/rq2/` and `data/rq3/`: mask and logical-job manifests.
- `src/telemetry_suff/`: canonical schemas, deterministic renderers, validation, metrics, and bootstrap code.
- `scripts/`: model-input builders, scorers, and dataset audits.
- `DATASET_CARD.md`: construction, labels, scope, and known constraints.

## Install and verify

Python 3.11 or later is required.

```bash
uv sync --frozen --all-extras
uv run pytest
shasum -a 256 -c DATASET_SHA256SUMS.txt
```

On Linux, use `sha256sum -c DATASET_SHA256SUMS.txt` for the final command.

## Build model inputs

Run these commands from the repository root:

```bash
uv run python scripts/build_rq1_jobs.py
uv run python scripts/build_rq2_jobs.py
uv run python scripts/build_rq3_requests.py
```

Generated model-visible requests are written to `outputs/requests/`. Gold-bearing manifests used only for scoring are written to `outputs/private/`. The fixed RQ2 panel contains Full, seven leave-one-factor-out masks, and the I+D+P+V, D+P+V, and S+V+T subsets.

The expected reconstruction counts are 1,872 RQ1 requests, 1,056 RQ2 discovery requests, and 2,376 RQ2 confirmation requests. For each RQ3 prompt policy, the discovery split contains 288 logical rows represented by 216 unique requests, and the confirmation split contains 576 logical rows represented by 432 unique requests.

## Bring your own model runner

The release does not prescribe an inference client. For each JSONL row in `outputs/requests/`, send only the supplied `system` and `user` fields, or the supplied `model_visible_payload`, to the model under test. Save one JSON object per line with the same `request_id` and a parsed `prediction` object. The scorers map `request_id` back to the private logical job. Keep model identity, decoding settings, and run metadata in a separate experiment manifest.

RQ1 predictions use `is_fault`, `fault_type`, `origin_component`, `origin_event_id`, `answerability`, and `confidence`. RQ2 predictions use `fault_present`, `fault_type`, `answerability`, `origin_component`, and `origin_event_id`. RQ3 predictions use `answerability`, `origin_component`, and `origin_event_id`. Invalid or incomplete objects remain in the denominator and receive no correctness credit.

## Score normalized predictions

```bash
uv run python scripts/score_rq1.py --predictions PATH.jsonl
uv run python scripts/score_rq2.py --predictions PATH.jsonl
uv run python scripts/score_rq3.py --jobs data/rq3/manifests/rq3_confirmation_logical_jobs.jsonl --predictions PATH.jsonl
```

The scorers do not make network calls. Generated `outputs/` are intentionally excluded from the release so that gold-bearing private manifests and local model runs are not committed accidentally.

## Citation

Citation metadata is provided in `CITATION.cff`. Until the paper receives final proceedings metadata, cite this artifact as:

> Yuxuan Zhu and Peng Pu. *TelemetrySuffBench: Is Agent Telemetry Sufficient for Failure-Origin Diagnosis?* Version 1.0.0, 2026. <https://github.com/amourlion/TelemetrySuffBench>

## Licenses and attribution

The source code and documentation are released under the MIT License in `LICENSE`. Files under `data/` and `DATASET_CARD.md` are released under CC BY 4.0 as stated in `LICENSE-DATA`.

The controlled traces were emitted through the public AgentTelemetry instrumentation API at source revision `246838d474114b41e5d3d68bb327e5c462a65d92`. AgentTelemetry is maintained by Krishna Chaitanya Balusu and licensed under Apache-2.0. This repository does not redistribute the AgentTelemetry source code.
