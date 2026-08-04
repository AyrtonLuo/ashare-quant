# Research Artifact Specification (Phase 7B)

## 1. Directory Structure & Layout
Research run artifacts are stored in isolated per-run directories:

```
data/research/runs/<research_run_id>/
├── run_metadata.json          # ResearchRunIdentity metadata
├── input_manifest.json        # ResearchInputManifest
├── result_manifest.json       # ResearchResultManifest
├── artifacts.json             # Core lightweight output payloads
├── signals.parquet            # Optional detailed signal series
├── positions.parquet          # Optional portfolio positions
├── trades.parquet             # Optional executed trades
├── equity_curve.parquet       # Optional daily equity curve
├── performance.json           # Detailed performance metrics
└── drawdown.json              # Drawdown analytics
```

## 2. Git Isolation Rules
Large parquet and database binary files are strictly excluded from Git via `.gitignore`:
- `data/research/`
- `*.parquet`
- `*.db`

Only manifests, metadata schemas, code specifications, and unit tests are tracked in Git.

## 3. Tampering Detection
Every artifact is hashed using canonical serialization (`compute_canonical_sha256`). If an artifact file on disk is altered or corrupted, `ResearchReplayEngine` or `ResearchResultComparator` detects the SHA-256 mismatch and fails closed.
