# Research Reproducibility Specification (Phase 7B)

## 1. Executive Summary
The core mandate of Phase 7B is upgrading `ashare-quant` from a Point-in-Time correct engine to a **100% Deterministic & Auditable Research Platform**. 

The fundamental immutability formula is:
$$\text{SAME DATA} + \text{SAME SNAPSHOT} + \text{SAME PARAMETERS} + \text{SAME CODE VERSION} + \text{SAME FACTOR DEFINITIONS} + \text{SAME COST MODEL} + \text{SAME UNIVERSE} = \text{SAME RESEARCH RESULT}$$

## 2. Research Run Identity & Lock Protocol

### 2.1 `ResearchRunIdentity`
Every research experiment and backtest run generates an immutable `ResearchRunIdentity` (`src/quant/reproducibility/identity.py`) capturing:
- `research_run_id`: Unique identifier for the research execution.
- `snapshot_id`: Locked snapshot identifier.
- `dataset_version`: Locked dataset version.
- `dataset_manifest_hash`: SHA-256 hash of dataset manifest.
- `as_of`: Locked query point-in-time cutoff.
- `universe_hash`: SHA-256 hash of evaluated universe.
- `factor_definition_hash`: SHA-256 hash of factor definitions & versions.
- `parameter_hash`: SHA-256 hash of strategy parameters.
- `transaction_cost_model_hash`: SHA-256 hash of cost model config.
- `benchmark_id`: Benchmark identifier.
- `code_version` & `code_state`: Git commit hash and working tree state (`CLEAN`, `DIRTY`, `UNAVAILABLE`).
- `input_hash` & `result_hash`: Cryptographic SHA-256 hashes.

### 2.2 `DatasetVersionLock`
Research runs lock `dataset_version` and `snapshot_id` at run initialization. Auto-fetching latest data or `datetime.now()` fallbacks are strictly prohibited and fail closed.

## 3. Canonical Serialization & SHA-256 Hashing
To prevent hash discrepancies caused by dictionary key ordering or floating point formatting, all manifest and artifact hashing passes through `to_canonical_json` and `compute_canonical_sha256` (`src/quant/reproducibility/canonical.py`).

## 4. Replay & Comparison Engine
- `ResearchReplayEngine`: Loads `ResearchInputManifest`, locks snapshot and dataset version, re-executes the backtest, and verifies 100% result hash match (`ReplayStatus.REPRODUCIBLE`).
- `ResearchResultComparator`: Compares two runs and outputs explicit human-readable diff explanations (`DIFFERENT_INPUT: parameter_hash differs`).

## 5. Fail-Closed Policy
If a dataset version, snapshot, factor version, or artifact is missing, tampered with, or un-verified, the engine **FAILS CLOSED** immediately. Silent fallbacks, `fillna(0)`, and un-locked research runs are forbidden.
