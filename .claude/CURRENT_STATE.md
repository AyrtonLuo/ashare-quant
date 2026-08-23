# Current Project State

## Current Phase
RIGHTS_OFFERING (配股) Adjustment — Implemented & Verified, pending CEO review (no phase number
assigned — explicitly not "Phase 10" per standing CEO instruction; this is a scoped follow-up
item from the post-Phase-9 read-only next-work scan, not a new roadmap phase)
Phase 9 — Research Result Persistence Hardening (Completed & Verified, core + Application Layer addendum)
Phase 8R — Certified Research Workbench UI & Mandatory Research Integrity Enforcement (Completed & Verified)
Phase 2 — Context System Hardening & Multi-Agent Handoff Protocol (Completed & Verified)

## Overall Status
Production-grade A-Share Quantitative Research & Backtesting Platform. Fully certified for Point-in-Time (PIT) temporal data integrity, immutable dataset locking (`ds_live_v4.0`), SHA-256 reproducibility, factor orchestration, zero-secret security auditing, web-based research workbench UI, durable persistence of certified `BacktestResult` scalar metrics, and now all four corporate-action types (`STOCK_SPLIT`/`BONUS_ISSUE`/`CASH_DIVIDEND`/`RIGHTS_OFFERING`) supported by `CorporateActionAdjuster`. 336/336 baseline tests passing 100% green (11 live-provider network tests safely skipped when live credentials are absent).

Context System hardened with Context Budget Protocol, State Machine (`NORMAL` -> `CONTEXT_PRESSURE` -> `HANDOFF_READY` -> `RECOVERY`), Multi-Agent Role Map (CEO / CTO / Coder), and Anti-Pollution Rules.

## Recently Completed
- **RIGHTS_OFFERING (配股) adjustment**: `CorporateActionAdjuster` now implements the last previously-unimplemented corporate-action type. `CorporateActionContract` gained trailing-defaulted `rights_ratio`/`subscription_price` fields; `_event_factor()` computes `(P + rights_ratio·subscription_price)/(P·(1+rights_ratio))`, the standard 配股除权价 formula through the same single-reference-price substitution already used for `CASH_DIVIDEND`. Fail-closed on missing/non-positive `rights_ratio`/`subscription_price`/reference price; `subscription_price >= reference_price` deliberately allowed (CEO-confirmed). 14 new tests (formula correctness, both boundary cases, 5 fail-closed paths, PIT exclusion, backward-compatible construction, certified-run consumption, replay reproducibility, 2 combined-same-`ex_date` tests). Zero changes to `result_hash`, identity, `CertifiedReplayEngine`, `BacktestEngine`, or PIT gating. Design doc: `RIGHTS_OFFERING_ADJUSTMENT_ARCHITECTURE_PROPOSAL.md` (revision 2, CEO-approved). Commits: `2d67834` (proposal), `c13955e` (implementation).
- **Phase 9 (core + Application Layer addendum)**: `ResearchResultManifest` extended with `schema_version` + 8 trailing-defaulted scalar metric fields, populated by `CertifiedResearchRunExecutor.execute()`; `ResearchRunStore.create_run()` writes now atomic; `get_run()` fails closed on corruption; new opt-in `verify_result_manifest_integrity()`. `research_application.py::get_research_run` migrated to read canonical fields, falling back to `workbench_metrics/` only for legacy runs. `result_hash`/Replay unaffected throughout. See `docs/PHASE_9_REPORT.md`.
- **Phase 2 Context Hardening**: Hardened `CLAUDE.md`, `.claude/CURRENT_STATE.md`, `.claude/DECISIONS.md`, and `.claude/HANDOFF.md` with multi-agent handoff contracts, budget state machine, and recovery protocols.
- **Phase 8R**: Certified Research Workbench UI, application layer, safety boundary enforcement, multi-factor orchestration UI integration.
- **Phase 8A**: Factor engine orchestration, certified replay integration, and backtest portfolio weight hardening.
- **Phase 7A–7J**: Historical PIT temporal architecture, snapshot immutability, revision non-destructiveness, survivorship-bias-free historical universe, corporate action binding, cross-provider reconciliation, and persistent dataset certification.

## Currently In Progress
- Awaiting CEO Review of the RIGHTS_OFFERING implementation.

## Two disclosed, pre-existing gaps explicitly NOT addressed by the RIGHTS_OFFERING work (per CEO scope instruction, flagged not hidden)
- **PIT gating for corporate actions checks `available_at` only** — `received_at` is captured on `CorporateActionContract` but never enforced by `PITGate.filter_pit_corporate_actions()` (contrast `filter_pit_fundamentals()`, which checks both). Pre-existing since Phase 7A, uniform across all four action types. Candidate for a future, separate PIT-hardening directive.
- **The existing per-type independent-factor-then-multiply implementation is not fully reconciled with `docs/CORPORATE_ACTION_SPECIFICATION.md`'s unified composite formula** for the combined-same-`ex_date` case (affects `CASH_DIVIDEND`/`BONUS_ISSUE`/`STOCK_SPLIT` combinations too, not just `RIGHTS_OFFERING`). See `RIGHTS_OFFERING_ADJUSTMENT_ARCHITECTURE_PROPOSAL.md` §3.3/§9. Candidate for a separate architectural review spanning all four types.

## Tests
- **Passed**: 336
- **Skipped**: 11 (Live provider network tests safely skipped when `TUSHARE_TOKEN` is absent in execution environment)
- **Failures**: 0
- **Test Command**: `PYTHONPATH=. ./venv/bin/pytest`

## Git Status
- **Branch**: `main`
- **Working Tree**: Clean.
- **Last Commit**: `c13955e` (`feat: implement RIGHTS_OFFERING (配股) adjustment per CEO-approved proposal`)

## Known Issues
- **Live Provider Network Credential Access**: Live network API calls to TuShare Pro require `TUSHARE_TOKEN` in environment. When absent, preflight safely skips live tests (`LIVE_PROVIDER_CREDENTIALS_UNAVAILABLE`), maintaining 100% pass rate on local production pipelines without fabricating data.
- **Numerical precision ceiling (disclosed, Phase 9)**: `ResearchRunStore.create_run()` rounds every persisted float to 6 decimals via `to_canonical_json` (pre-existing since Phase 7I). Harmless in practice since `BacktestEngine` already rounds to 4 decimals before `BacktestResult` is built.
- See "Two disclosed, pre-existing gaps" above for the two items surfaced during RIGHTS_OFFERING review.
- **`docs/ROADMAP.md` is stale** (v1.0.0, `CEO-2026-08-01-REBUILD-001`) — its 12-phase linear plan diverged from actual execution long ago, and its "Phase 10/11/12" labels (Paper Trading/Broker/Live Trading) conflict with `CLAUDE.md`'s absolute scope boundary. Flagged for documentation governance (CEO decision, not yet actioned).
- **`turnover`/`trade_count` remain placeholder values** in `BacktestEngine` (`turnover=0.15` hardcoded, `trade_count=len(daily_returns)`) — real fix requires multi-period rebalancing semantics design; explicitly not authorized (CEO decision, post-Phase-9 scan).

## Important Files
- `CLAUDE.md` — Project context directive, context budget protocol, state machine, and multi-agent protocol.
- `.claude/CURRENT_STATE.md` — Single-page active snapshot of project state, tests, and git status.
- `.claude/DECISIONS.md` — Permanent architectural memory and core design decisions.
- `.claude/HANDOFF.md` — Standardized multi-agent handoff contract.
- `RIGHTS_OFFERING_ADJUSTMENT_ARCHITECTURE_PROPOSAL.md` — RIGHTS_OFFERING design doc (repo root), CEO-approved, revision 2.
- `src/quant/adjustment/corporate_action_adjuster.py` — all four corporate-action types now implemented.
- `src/data/contracts/corporate_action.py` — `CorporateActionContract`, now with `rights_ratio`/`subscription_price`.
- `src/quant/reproducibility/` — Canonical SHA-256 identity, input/result manifests, replay engine, `ResearchRunStore`.
- `src/data/snapshot/snapshot_manager.py` — PIT snapshot isolation.
- `src/quant/factors/` — Value, Momentum, Volatility, Liquidity factor adapters & multi-factor engine.
- `src/quant/backtest/engine.py` — Backtest engine with snapshot and dataset version locking.
- `docs/PHASE_9_REPORT.md`, `docs/PHASE_8R_REPORT.md` — Prior phase deliverable reports.
- `docs/CORPORATE_ACTION_SPECIFICATION.md` — Corporate-action formula specification.
- `docs/FINAL_RESEARCH_INTEGRITY_CERTIFICATION.md` — Final Research Integrity Certification.

## Next Recommended Action
Wait for CEO Review of the RIGHTS_OFFERING implementation. No further work authorized until then. Do NOT implement trading, broker connections, or live order routing. Do NOT create a "Phase 10."
