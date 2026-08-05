# Current Project State

## Current Phase
Phase 9 — Research Result Persistence Hardening (Implemented & Verified; pending CEO review)
Phase 8R — Certified Research Workbench UI & Mandatory Research Integrity Enforcement (Completed & Verified)
Phase 2 — Context System Hardening & Multi-Agent Handoff Protocol (Completed & Verified)

## Overall Status
Production-grade A-Share Quantitative Research & Backtesting Platform. Fully certified for Point-in-Time (PIT) temporal data integrity, dual cutoff enforcement (`available_at <= as_of` AND `received_at <= as_of`), immutable dataset locking (`ds_live_v4.0`), SHA-256 reproducibility, factor orchestration, zero-secret security auditing, web-based research workbench UI, and now durable persistence of certified `BacktestResult` scalar metrics (not just their hash). 319/319 baseline tests passing 100% green (11 live-provider network tests safely skipped when live credentials are absent).

Context System hardened with Context Budget Protocol, State Machine (`NORMAL` -> `CONTEXT_PRESSURE` -> `HANDOFF_READY` -> `RECOVERY`), Multi-Agent Role Map (CEO / CTO / Coder), and Anti-Pollution Rules.

## Recently Completed
- **Phase 9**: `ResearchResultManifest` extended with `schema_version` + 8 trailing-defaulted scalar metric fields (`total_return`, `sharpe_ratio`, `max_drawdown`, etc.); `CertifiedResearchRunExecutor.execute()` now populates them from the real `BacktestResult`; `ResearchRunStore.create_run()` writes are now atomic (temp-dir + `os.rename`); `get_run()` fails closed with a clear error on corrupted files instead of an opaque `JSONDecodeError`; new opt-in `verify_result_manifest_integrity()`. `result_hash`'s definition/computation point is unchanged; Replay unaffected (verified both behaviorally and via static source check). 15 new tests, 0 existing tests modified. See `docs/PHASE_9_REPORT.md` and `PHASE_9_RESEARCH_RESULT_PERSISTENCE_ARCHITECTURE_PROPOSAL.md`.
- **Phase 2 Context Hardening**: Hardened `CLAUDE.md`, `.claude/CURRENT_STATE.md`, `.claude/DECISIONS.md`, and `.claude/HANDOFF.md` with multi-agent handoff contracts, budget state machine, and recovery protocols.
- **Phase 8R**: Certified Research Workbench UI, FastAPI application layer, safety boundary enforcement, multi-factor orchestration UI integration, and 304 passing tests.
- **Phase 8A**: Factor engine orchestration, certified replay integration, and backtest portfolio weight hardening.
- **Phase 7A–7J**: Historical PIT temporal architecture, snapshot immutability, revision non-destructiveness, survivorship-bias-free historical universe, corporate action binding, cross-provider reconciliation, and persistent dataset certification.

## Recently Completed (continued)
- **Phase 9 Application Layer follow-up (addendum)**: `research_application.py::get_research_run` now reads display metrics from the canonical `result_manifest` fields (`schema_version >= "2.0"`) via a new `_resolve_metrics()` helper, falling back to the `workbench_metrics/` side cache only for legacy (`schema_version == "1.0"`) runs. `_save_metrics()`/the cache write path is untouched (not retired). No changes to `CertifiedReplayEngine`, `BacktestEngine`, or identity/hash logic. 3 new tests, 0 existing tests modified. See `docs/PHASE_9_REPORT.md` §6 (addendum).

## Currently In Progress
- Awaiting CEO Review of Phase 9 (core + Application Layer addendum).

## Tests
- **Total Tests Collected**: 333
- **Passed**: 322
- **Skipped**: 11 (Live provider network tests safely skipped when `TUSHARE_TOKEN` is absent in execution environment)
- **Failures**: 0
- **Test Command**: `PYTHONPATH=. ./venv/bin/pytest`

## Git Status
- **Branch**: `main`
- **Working Tree**: Application Layer addendum present (`src/app/research_application.py` + 2 test files modified) — commit pending.
- **Last Commit**: `723d2a3` (`docs: update phase 9 report with final commit hash`)

## Known Issues
- **Live Provider Network Credential Access**: Live network API calls to TuShare Pro require `TUSHARE_TOKEN` in environment. When absent, preflight safely skips live tests (`LIVE_PROVIDER_CREDENTIALS_UNAVAILABLE`), maintaining 100% pass rate on local production pipelines without fabricating data.
- **Numerical precision ceiling (disclosed, Phase 9)**: `ResearchRunStore.create_run()` rounds every persisted float to 6 decimals via `to_canonical_json` (pre-existing since Phase 7I). Harmless in practice since `BacktestEngine` already rounds to 4 decimals before `BacktestResult` is built, but documented/tested as a real ceiling, not "unlimited precision."

## Important Files
- `CLAUDE.md` — Project context directive, context budget protocol, state machine, and multi-agent protocol.
- `.claude/CURRENT_STATE.md` — Single-page active snapshot of project state, tests, and git status.
- `.claude/DECISIONS.md` — Permanent architectural memory and core design decisions.
- `.claude/HANDOFF.md` — Standardized multi-agent handoff contract.
- `src/quant/reproducibility/` — Canonical SHA-256 identity, input/result manifests (Phase 9: now carries real scalar metrics), replay engine, `ResearchRunStore` (Phase 9: atomic writes, fail-closed corruption handling).
- `src/data/snapshot/snapshot_manager.py` — Dual cutoff PIT snapshot isolation.
- `src/data/revision/revision_store.py` — Non-destructive revision store.
- `src/quant/factors/` — Value, Momentum, Volatility, Liquidity factor adapters & multi-factor engine.
- `src/quant/backtest/engine.py` — Backtest engine with snapshot and dataset version locking.
- `src/web/app.py` — FastAPI Research Workbench backend server.
- `docs/PHASE_9_REPORT.md` — Phase 9 Executive Deliverable Report.
- `PHASE_9_RESEARCH_RESULT_PERSISTENCE_ARCHITECTURE_PROPOSAL.md` — Phase 9 architecture proposal (repo root).
- `docs/PHASE_8R_REPORT.md` — Phase 8R Executive Deliverable Report.
- `docs/FINAL_RESEARCH_INTEGRITY_CERTIFICATION.md` — Final Research Integrity Certification.

## Next Recommended Action
Wait for CEO Review of Phase 9. If approved, next candidate directive is the deferred Application Layer follow-up (§6 of `docs/PHASE_9_REPORT.md`) — not authorized to implement without a directive. Do NOT implement trading, broker connections, or live order routing.
