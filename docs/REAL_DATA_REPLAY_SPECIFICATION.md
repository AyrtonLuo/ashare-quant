# Real Data Replay Specification (Phase 7C)

## 1. Overview
The Real Data Replay Protocol guarantees that any historical backtest run over real market datasets can be re-executed at any future date to produce **100% identical SHA-256 result hashes**.

## 2. Replay Verification Flow
1. **Load Research Run Identity**: Retrieve `ResearchRunIdentity` from `ResearchRunStore`.
2. **Dataset Version Lock**: Lock `dataset_version` and `snapshot_id` using `DatasetVersionLock`.
3. **Parameter Lock**: Restore exact universe, factor configurations, strategy parameters, and transaction cost models.
4. **Re-execution**: Run `BacktestEngine.run_backtest()` using `ResearchDataAPI`.
5. **Hash Matching**: Compute canonical SHA-256 hash of replayed output payload.
6. **Verdict**: If `replayed_hash == original_hash`, return `ReplayStatus.REPRODUCIBLE`. Otherwise fail closed with `ReplayStatus.MISMATCH`.
