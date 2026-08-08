# Release Checklist for v1.0.0

- [x] Add the MIT software license and CC BY 4.0 dataset license.
- [x] Replace the repository URL in this repository and the paper.
- [x] Freeze the main dataset, seeded holdout, split files, and protocol manifests as version 1.0.0.
- [x] Verify all 544 entries in `DATASET_SHA256SUMS.txt`.
- [x] Create a clean Python 3.11 environment and run `pytest`.
- [x] Rebuild all RQ1, RQ2, and RQ3 requests from the released data.
- [x] Confirm that generated request counts match the paper and `RELEASE_MANIFEST.json`.
- [x] Scan tracked files for credentials, inference endpoints, local absolute paths, request histories, response transcripts, and deployment-specific configuration.
- [x] Confirm that generated `outputs/` and environment files are excluded from the release commit.
- [x] Exclude model outputs from version 1.0.0.
- [x] Add citation metadata and continuous-integrity checks.
- [x] Tag the exact release commit as `v1.0.0`.

Validated on 2026-08-08. The tag item is completed by the publication commit that contains this checklist.
