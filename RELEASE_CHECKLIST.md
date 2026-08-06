# Release Checklist

- [ ] Select and add the final open-source license.
- [x] Replace the repository URL in this repository and the paper.
- [ ] Confirm the final dataset and protocol versions.
- [ ] Regenerate and verify `DATASET_SHA256SUMS.txt`.
- [ ] Create a clean environment and run `pytest`.
- [ ] Rebuild all RQ1, RQ2, and RQ3 requests from the released data.
- [ ] Confirm that generated request counts match the paper.
- [ ] Scan the release tree for credentials, endpoints, local absolute paths, request histories, response transcripts, and deployment-specific configuration.
- [ ] Confirm that no generated `outputs/` directory is included in the release commit.
- [ ] Add model outputs only after they have passed the same release scan.
- [ ] Tag the exact commit cited by the paper.
