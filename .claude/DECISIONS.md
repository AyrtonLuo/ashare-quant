# Architecture Decisions

## Decision: Point-in-Time (PIT) Dual Cutoff Temporal Isolation Enforcement

### Status
Accepted

### Decision
All queries, factor computations, and backtests must strictly filter data using dual cutoff semantics: `available_at <= as_of` AND `received_at <= as_of`. No future revisions or backfills may mutate past historical snapshots.

### Reason
To prevent lookahead bias, survivorship bias, and backtest data contamination. Quantitative research must strictly answer: "What exact data was known and available at historical timestamp T?"

### Alternatives Considered
- Single cutoff filtering on `effective_date` (Rejected: cause lookahead leaks when data is published with delay).
- In-place mutation of market data tables (Rejected: destroys historical auditability).

### Consequences
- Historical factor computations are 100% immune to future revisions.
- `SnapshotManager` builds reproducible PIT datasets anchored to immutable dataset versions (`ds_live_v4.0`).

---

## Decision: Immutable Research Run Identity & SHA-256 Replay Reproducibility

### Status
Accepted

### Decision
Every backtest or research experiment generates a cryptographically bound `ResearchRunIdentity` containing canonical SHA-256 hashes of input manifests (dataset version, snapshot ID, factor config, strategy parameters, cost model, universe, code version/commit, working tree status) and result manifests. Replaying a run must yield an identical SHA-256 result hash (`ReplayStatus.REPRODUCIBLE`).

### Reason
To ensure 100% research reproducibility across different environments, sessions, or execution times.

### Alternatives Considered
- Storing unhashed raw backtest output files without manifest binding (Rejected: impossible to verify if code or data changed).
- Dynamic `datetime.now()` default fallback for research runs (Rejected: breaks determinism).

### Consequences
- Overwriting existing research runs fails closed (`ValueError: FAIL CLOSED: Research Run ID already exists and is IMMUTABLE`).
- Research runs are permanently reproducible and audit-verifiable.

---

## Decision: Research Integrity Safety Boundary & Strict No-Trading Policy

### Status
Accepted

### Decision
The repository is explicitly restricted to Historical Data, PIT Research, Factor Engineering, Backtesting, and Research Workbench UI. Implementation of live trading APIs, broker connections, order routing, paper trading, automatic buy/sell, or real-money execution is strictly forbidden.

### Reason
To preserve the system purely as a scientific quantitative research and data integrity platform, eliminating operational risk and unauthorized execution.

### Alternatives Considered
- Integrating paper trading or broker execution components (Rejected: violates scope boundaries and introduces live operational hazard).

### Consequences
- Platform remains clean, audit-friendly, and focused on institutional-grade quant research integrity.

---

## Decision: DataTrustGate Validation & Zero-Secret Security Auditing

### Status
Accepted

### Decision
All provider data must pass through `DataTrustGate` before entering factor or backtest engines. Un-verified or current-only metrics must return `FactorStatus.NOT_APPLICABLE` (raw_value = None) with ZERO silent `fillna(0)` fallbacks. Additionally, `SecurityAuditManager` recursively scans manifests, logs, and artifacts for zero secret/token leakage.

### Reason
Silent zero-filling distorts financial ratios (e.g. PE, PB) and creates phantom alpha. Exposing API credentials (`TUSHARE_TOKEN`) in logs or git commits poses critical security risks.

### Alternatives Considered
- Silent default filling (`fillna(0)` or forward-filling across unverified PIT boundaries) (Rejected: corrupts factor math).
- Manual code review for secret leaks (Rejected: error-prone; automated scanner required).

### Consequences
- High-integrity data pipeline that fails closed on invalid data and guarantees zero secret leakage.

---

## Decision: Certified Research Workbench UI Architecture

### Status
Accepted

### Decision
Build a lightweight, web-based research workbench using HTML/JS/CSS frontend served by FastAPI application layer (`src/web/app.py`), directly bound to certified backtest engines, factor analytics, and research run stores.

### Reason
Provides an interactive research environment for quant analysts to visualize factor performance, equity curves, drawdown metrics, and replay audits without risking code state or backend contracts.

### Alternatives Considered
- Heavy desktop GUI (Rejected: unnecessary complexity and maintenance overhead).
- Third-party web dashboards (Rejected: risk of bypassing PIT contracts).

### Consequences
- Clean separation of UI presentation from quant backtest logic while enforcing safety boundaries.

---

## Decision: Lightweight Git-Tracked Context Management Protocol

### Status
Accepted

### Decision
Adopt a lightweight, file-based context protocol (`CLAUDE.md`, `.claude/CURRENT_STATE.md`, `.claude/DECISIONS.md`, `.claude/HANDOFF.md`) instead of heavy external memory frameworks (Mem0, claude-mem, vector DBs).

### Reason
Chat conversation context is temporary and volatile. Git-tracked context files provide a zero-dependency, multi-agent, compaction-resistant source of truth that is fully inspectable, diffable, and version-controlled.

### Alternatives Considered
- Installing third-party memory systems (Mem0, MCP memory servers) (Rejected: introduces external dependencies, potential secret leaks, and maintenance overhead).
- Relying solely on chat transcripts (Rejected: context limits erase project state).

### Consequences
- Cross-session and multi-agent state continuity guaranteed with zero code/dependency bloat.

---

## Decision: Phase 9 — Extend `ResearchResultManifest` for Result Persistence (Option A)

### Status
Accepted

### Decision
Persist `BacktestResult`'s real scalar metrics (`total_return`, `sharpe_ratio`, `max_drawdown`, etc.) as trailing-defaulted `Optional` fields directly on the existing `ResearchResultManifest` dataclass, written through the existing `ResearchRunStore.create_run()` mechanism. `result_hash`'s definition and computation point remain frozen exactly as before; a new, separate, opt-in `verify_result_manifest_integrity()` function checks the persisted manifest against `identity.result_hash` without redefining what the hash covers. Atomic writes (temp-dir + `os.rename`) and fail-closed corruption detection were added to `ResearchRunStore` in the same pass, since both are pre-existing gaps in the exact code path already being touched.

### Reason
The gap was a contract-completeness problem, not a storage/serialization/process-boundary defect — `CertifiedResearchRunExecutor.execute()` simply never placed the real numbers into anything handed to `create_run()`. Extending the existing, already-proven, typed persistence contract follows this project's own established precedent (Phase 8A's `signal_configuration_hash` trailing-default addition) rather than introducing new storage infrastructure. Full analysis: `PHASE_9_RESEARCH_RESULT_PERSISTENCE_ARCHITECTURE_PROPOSAL.md`; implementation report: `docs/PHASE_9_REPORT.md`.

### Alternatives Considered
- **Dedicated `CanonicalResultStore`** (a new class, a new sibling file per run) (Rejected: introduces a second write path and a new cross-file consistency risk — "did both writes succeed?" — for no corresponding benefit over extending the existing single-write manifest).
- **Extend the untyped `artifacts` dict** with a `"backtest_metrics"` key (Rejected: weaker typing, no dataclass-level schema guarantee, blurs the existing "inputs a replay needs" vs. "the certified result itself" distinction).

### Consequences
- A fresh process, given only a `research_run_id`, can now read back the exact certified numeric result — closing the gap that previously required the non-canonical, Phase-8R-owned `workbench_metrics/` UI side cache.
- Legacy runs (`schema_version == "1.0"`) correctly read the new fields as `None`, never fabricated as `0.0` — consistent with this project's Anti-Fabrication principle.
- Deferred, not decided here: whether `src/app/research_application.py` should be updated to prefer these canonical fields over `workbench_metrics/` — left to a future directive (see `docs/PHASE_9_REPORT.md` §6).
