# Agent Handoff

## Handoff Status
READY

## Current Phase
RIGHTS_OFFERING (配股) Adjustment — Implemented & Verified, pending CEO review. No phase number
assigned — explicitly not "Phase 10" per standing CEO instruction; this was a scoped follow-up
item identified by a post-Phase-9 read-only next-work scan, approved item #1 of 3 candidates.

## Current Objective
Implementation delivered and committed per CEO-approved Revision 2 proposal
(`RIGHTS_OFFERING_ADJUSTMENT_ARCHITECTURE_PROPOSAL.md`). All CEO-mandated verification steps
complete. STOP — awaiting CEO Review, per explicit instruction. Do not proceed further, do not
create a "Phase 10," do not expand scope.

## Completed
- **RIGHTS_OFFERING (配股) adjustment** (commits `2d67834` proposal, `c13955e` implementation):
  `CorporateActionAdjuster` now implements the last previously-unimplemented corporate-action
  type (previously failed closed unconditionally). `CorporateActionContract` gained two
  trailing-defaulted `Optional[float]` fields, `rights_ratio`/`subscription_price` — zero ripple
  to all 14 existing construction call sites. `_event_factor()`'s new branch computes
  `(P + rights_ratio·subscription_price) / (P·(1+rights_ratio))` — the standard 配股除权价
  formula through the same single-reference-price substitution already used for
  `CASH_DIVIDEND`. Fail-closed on missing `rights_ratio`/`subscription_price` (never fabricated
  as `0.0`), `rights_ratio <= 0`, `subscription_price <= 0`, non-positive reference price.
  `subscription_price >= reference_price` deliberately **not** an error (CEO-confirmed —
  produces a well-defined `factor >= 1.0`). 14 new tests per the proposal's §6 matrix: formula
  correctness, both boundary cases, 5 fail-closed paths, PIT exclusion via `available_at`,
  backward-compatible construction, end-to-end certified-run consumption, replay
  reproducibility, and 2 combined-same-`ex_date` tests (rights+dividend, rights+bonus) proving
  the product-of-independent-factors mechanism. Zero changes to `result_hash`, identity,
  `CertifiedReplayEngine`, `BacktestEngine`, or PIT gating logic.
- **Phase 9 (core + Application Layer addendum)**: `ResearchResultManifest` extended with
  `schema_version` + 8 trailing-defaulted scalar fields, populated by
  `CertifiedResearchRunExecutor.execute()`; `ResearchRunStore` atomic writes + fail-closed
  corruption handling; `research_application.py::get_research_run` migrated to canonical-field
  reads. Committed as `4267912`/`77191b9`/docs commits. See `docs/PHASE_9_REPORT.md`.
- **Phase 1 – Phase 8R Implementation**: certified research workbench, PIT dual-cutoff isolation
  (for fundamentals — see Known Issue below re: corporate actions), factor orchestration.
- **Phase 2 Context System Hardening**: `CLAUDE.md` budget protocol, state machine, role map.

## Verification performed for the RIGHTS_OFFERING implementation (all CEO-mandated steps)
- Full `pytest`: **336 passed, 11 skipped, 0 failed** (up from 322/11/0 — exactly +14, matching
  the proposal's test matrix, 0 existing tests modified).
- `git diff --check`: clean (no whitespace errors).
- Second-round read-only audit: diff re-read line-by-line against the approved proposal; formula,
  fail-closed order, and the `SUPPORTED_ADJUSTING_ACTION_TYPES` carve-out removal all verified.
- Scope check: `git diff --stat` shows exactly 4 files (`corporate_action.py`,
  `corporate_action_adjuster.py`, and their 2 test files) — confirmed empty diff for
  `src/quant/reproducibility/`, `src/quant/backtest/`, `certified_replay_engine.py`,
  `integrity_gate.py`, `pit_gate.py`.
- Secret scan: project's own regex sweep (sk-/AKIA/xox/PRIVATE KEY/ghp_ patterns) — no matches.
- Trading-boundary check: grepped diff for broker/order/execute-trade keywords — none.
- No test weakened, skipped, or xfail'd to pass — grepped diff for `.skip(`/`xfail` — none.

## Not Completed
- No open RIGHTS_OFFERING items remain — implementation matches the approved proposal exactly.
- Two items explicitly surfaced and explicitly NOT addressed, per CEO scope instruction (flagged,
  not hidden — see `RIGHTS_OFFERING_ADJUSTMENT_ARCHITECTURE_PROPOSAL.md` §5/§3.3/§9):
  1. `PITGate.filter_pit_corporate_actions()` checks `available_at` only; `received_at` is
     captured but never enforced, for all four action types, since Phase 7A.
  2. The existing per-type independent-factor-then-multiply implementation is not reconciled
     with `docs/CORPORATE_ACTION_SPECIFICATION.md`'s unified composite formula for the
     combined-same-`ex_date` case (pre-existing, affects the 3 already-shipped types too).
- Future Research Directives (Awaiting CEO Review).

## Current Test Baseline
- **Passed**: 336
- **Skipped**: 11 (Live provider network tests safely skipped when `TUSHARE_TOKEN` is absent)
- **Failures**: 0
- **Test Command**: `PYTHONPATH=. ./venv/bin/pytest`

## Relevant Files
- `CLAUDE.md` — Operating directive, context budget protocol, state machine, multi-agent protocol.
- `.claude/CURRENT_STATE.md` — Single-page active snapshot of project state, tests, git status.
- `.claude/DECISIONS.md` — Permanent architectural memory and core design decisions.
- `.claude/HANDOFF.md` — Standardized multi-agent handoff contract.
- `RIGHTS_OFFERING_ADJUSTMENT_ARCHITECTURE_PROPOSAL.md` — CEO-approved design doc, revision 2.
- `src/quant/adjustment/corporate_action_adjuster.py`, `src/data/contracts/corporate_action.py`
  — the implementation.
- `docs/CORPORATE_ACTION_SPECIFICATION.md` — the specification this implementation was
  reconciled against (§3.3 of the proposal).
- `docs/PHASE_9_REPORT.md` — Phase 9 Executive Deliverable Report.
- `docs/PHASE_8R_REPORT.md` — Phase 8R Executive Deliverable Report.

## Important Decisions
- **PIT Filtering — corporate actions vs. fundamentals differ**: `filter_pit_fundamentals()`
  checks both `available_at` and `received_at`; `filter_pit_corporate_actions()` checks
  `available_at` only. This asymmetry is real, pre-existing, and now explicitly documented
  (previously under-described) — see `.claude/DECISIONS.md`.
- **RIGHTS_OFFERING formula — additive, not a rewrite**: same single-reference-price
  substitution pattern already used for `CASH_DIVIDEND`; introduces no new class of divergence
  from `docs/CORPORATE_ACTION_SPECIFICATION.md`. See `.claude/DECISIONS.md` and the proposal §3.
- **Absolute Scope Boundary**: Research, Factor Engineering, Backtesting, and Workbench UI ONLY.
  Zero broker or trading execution code allowed.
- **DataTrustGate & Zero Secrets**: Strict quality gate without `fillna(0)` fallbacks and zero
  secret leakage scanner (`SecurityAuditManager`).

## Constraints
- **NO Unrelated Refactoring / Unauthorized Architecture Mutations**: this change touched
  exactly the files the CEO-approved proposal named — do not expand into the two disclosed gaps
  above, `turnover`/`trade_count` realism, result-component hashes, or `docs/ROADMAP.md`
  governance without a new explicit directive.
- **NO Unsanctioned Memory Tools**: Do not install Mem0, claude-mem, MCP servers, or agent
  frameworks.
- **NO Credential Exposure**: Never log or commit API keys or tokens.
- **Commit locally is expected once verification is done; do NOT push to remote without explicit
  user approval.**

## Risks
- Context bloat if incoming agents bypass `CLAUDE.md` protocols and attempt repository-wide scans.
- An implementer might later be tempted to "clean up" the two disclosed pre-existing gaps
  (PIT `received_at`, spec-formula reconciliation) as drive-by fixes while touching this code —
  both are explicitly out of scope until a separate CEO directive authorizes them.

## Exact Next Action
Await CEO Review of the RIGHTS_OFFERING implementation. No further work authorized until then.
If a new directive is issued, execute the New Session Recovery Protocol starting with
`CLAUDE.md`.

## Do Not
- Do NOT implement live trading, broker connections, or order routing.
- Do NOT create a "Phase 10" or assign a phase number to this work.
- Do NOT expand into the two disclosed pre-existing gaps without a new directive.
- Do NOT push to the remote repository without explicit user approval.

## Validation Required
- Run `git status` to verify the working tree is clean (both commits already made).
- Verify 336 passing / 11 skipped / 0 failed via `PYTHONPATH=. ./venv/bin/pytest`.
