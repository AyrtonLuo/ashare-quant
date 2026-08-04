# Data Snapshot Specification (Phase 7)

## 1. Overview
The Data Snapshot engine (`src/data/snapshot/`) provides an immutable, audit-verifiable logical view of the data world as of a specific cutoff timestamp `as_of = T`. 

A `DataSnapshot` guarantees that no strategy or research query can access data published or made available after `as_of`.

## 2. Core Data Structures

### 2.1 `DataSnapshot`
```python
@dataclass(frozen=True)
class DataSnapshot:
    snapshot_id: str                  # e.g., "snapshot_20220801_v1"
    as_of: datetime                   # Query point-in-time cutoff
    dataset_version: str              # Dataset version e.g., "ds_v1.0"
    provider_versions: Dict[str, str] # e.g., {"tushare": "2.0", "akshare": "1.0"}
    data_cutoff: datetime             # Strict data availability limit
    created_at: datetime              # Snapshot creation timestamp
    schema_version: str               # Schema version e.g., "1.0.0"
    manifest_hash: str                # SHA-256 hash of manifest
```

### 2.2 `SnapshotManifest`
```python
@dataclass(frozen=True)
class SnapshotManifest:
    snapshot_id: str
    dataset_manifest_hash: str
    schema_hash: str
    provider_manifest: Dict[str, Any]
    revision_policy: str
    as_of: datetime
    created_at: datetime
    code_version: str
    parameter_hash: str
    manifest_hash: str
```

## 3. Mandatory Query Semantics
All research and backtesting data access must be executed through `SnapshotManager` or `ResearchDataAPI` using PIT gating:
- `query_market_data(symbol, start, end, as_of, snapshot_id)`
- `query_fundamentals(symbol, as_of, snapshot_id)`
- `query_metric(symbol, metric, effective_date, as_of, snapshot_id)`
- `query_snapshot(snapshot_id)`

## 4. Immutability & Reproducibility Principle
Once a dataset version or snapshot is created, it is **IMMUTABLE**. Subsequent data updates, restatements, or provider backfills produce a **NEW REVISION** and **NEW DATASET VERSION**, leaving past snapshots completely untouched.
