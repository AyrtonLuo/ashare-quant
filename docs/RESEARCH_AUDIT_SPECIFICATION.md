# Research Audit Specification (Phase 7B)

## 1. Audit Framework & Certification Steps
To certify a research run as **AUDIT VERIFIED & REPRODUCIBLE**, quantitative auditors must execute the following 5-step verification process:

1. **Identity & Manifest Audit**: Retrieve `ResearchRunIdentity` and verify `input_hash` against `ResearchInputManifest`.
2. **Dataset & Snapshot Lock Audit**: Validate that `dataset_version` and `snapshot_id` are registered in `SnapshotManager` and `RevisionStore`. Confirm no `datetime.now()` or implicit fallbacks were used.
3. **Replay Audit**: Run `ResearchReplayEngine.replay_run(run_id)`. Verify `ReplayStatus == REPRODUCIBLE`.
4. **Comparator Audit**: Compare the run against benchmark baseline using `ResearchResultComparator.compare_runs()`.
5. **Git & Code Version Audit**: Inspect `code_version` git commit and verify `code_state == CLEAN`.

## 2. Audit Certification Matrix

| Audit Check | Pass Condition | Failure Protocol |
| :--- | :--- | :--- |
| **Dataset Lock** | `dataset_version` locked in snapshot | `FAIL CLOSED` |
| **Snapshot Lock** | `snapshot_id` registered & frozen | `FAIL CLOSED` |
| **Input Manifest Hash** | Cryptographically matches SHA-256 | `FAIL CLOSED` |
| **Result Manifest Hash** | Cryptographically matches SHA-256 | `FAIL CLOSED` |
| **Replay Hash Match** | Replayed output hash equals original | `FAIL CLOSED` |
| **Git Code State** | `git_commit` recorded | Record `DIRTY` if working tree modified |
