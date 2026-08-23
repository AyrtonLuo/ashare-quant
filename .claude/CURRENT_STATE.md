# Current Project State

_Synchronized to HEAD `33296e7`. Authority order per `CLAUDE.md` §2:
Actual Repository Code & Specs > Automated Test Suite > this file > Conversation History._

## Current Track
**AI Quant Research Analyst** — evidence-grounded LLM research synthesis.
No phase number is assigned to this track (standing CEO instruction). **Phase 9 is complete.
Do NOT create a "Phase 10."**

Governing document: `AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md` (revision 2, repo root).
Its §11 Implementation Plan is the authoritative step list; steps 1–4 are delivered, steps 5–6
are not, and each remaining step requires its own explicit CEO directive.

## Overall Status
Production-grade A-Share Quantitative Research & Backtesting Platform: certified Point-in-Time
(PIT) temporal integrity with dual-cutoff (`available_at` AND `received_at`) enforcement across
fundamentals, revisions **and corporate actions**; immutable dataset locking (`ds_live_v4.0`);
SHA-256 reproducibility and certified replay; factor orchestration; zero-secret security
auditing; web-based research workbench UI; durable persistence of certified `BacktestResult`
scalar metrics; all four corporate-action types implemented, with an opt-in unified composite
adjustment formula.

On top of that base, the AI Research Analyst track has delivered the full deterministic chain
`API → Adapter → Contract → Validation → PIT → Evidence Bundle → LLM Provider → Structured
Output → Citation Validation`. **No live LLM API has been called or wired anywhere in this
codebase** — only deterministic fake providers exist.

## Completed — AI Research Analyst track
- **Data infrastructure** (`f75b0ef`): `NewsAnnouncementContract`; `NewsAnnouncementProvider` ABC
  + `NewsAnnouncementPage`; `SyntheticNewsAnnouncementProvider` (deterministic fixture) and
  `LiveNewsAnnouncementProvider` (explicit refusal — no live API wired); `DataTrustGate`
  extended with `validate_news_announcement()` / `validate_technical_indicator()`;
  `PITGate.filter_pit_news_announcements()` (additive; existing PIT methods unmodified).
- **Technical indicators** (`f75b0ef`): MA / RSI / MACD — real, deterministic, tested
  (`src/quant/technical/indicators.py`).
- **Evidence Layer** (`f75b0ef`): `EvidenceItem` (typed `FACT` / `MODEL_OUTPUT`), market /
  fundamental / news / technical assembly functions, `detect_duplicate_news()`, evidence-bundle
  hashing (`src/quant/evidence/evidence_item.py`).
- **LLM Provider interface layer** (`33296e7`, new package `src/llm/`, **zero existing files
  modified**):
  - `provider_base.py` — `LLMProvider` ABC (`provider_id` / `provider_version` + a single
    `generate_structured_research()`), `LLMRequest` / `LLMResponse` / `LLMTokenUsage`,
    `LLMErrorCategory` (8 categories) + `LLMProviderError` carrying an explicit category.
  - `structured_output.py` — `StructuredResearchOutput`, the 10-field schema, with
    `__post_init__` validation; `parse_structured_output()` is the fail-closed parsing boundary.
  - `citation_validator.py` — `validate_citations()`: deterministic code, **not** a second LLM
    call. Catches invented `evidence_id`s, evidence borrowed from another request's bundle, and
    untraceable numbers in prose. Disclosed limitation: numeric-hallucination scan, not full
    semantic fact-checking.
  - `credential.py` — `LLMProviderCredentialPreflight.inspect_credentials()`, generic over
    `provider_id` / env var name; reports `LLM_PROVIDER_CREDENTIALS_UNAVAILABLE`, never logs a
    key, never requires a real key to run.
  - `fake_provider.py` — `FakeLLMProvider` + `AlternateFakeLLMProvider`, two independently
    implemented deterministic doubles proving provider switching. No vendor SDK imported.
  - `research_analyst.py` — `generate_ai_research_output()`, the single call site;
    `AIResearchIdentity` records provider / model / model_version / prompt_version /
    evidence_bundle_hash / timeout / token usage. `LLMRequest`'s only content field is
    `evidence_payload`, so no data handle or search capability can structurally reach a provider.

## Completed — corporate-action follow-ups (since the previous sync at `c13955e`)
Both items previously recorded here as "disclosed, pre-existing gaps" are now **closed**:
- **`received_at` PIT enforcement** (`e100cda`): the audit found **two** independent gates that
  checked `available_at` only — `PITGate.filter_pit_corporate_actions()` **and**
  `CorporateActionStore.query_pit()` / `query_pit_range()`. Both now require
  `available_at <= as_of` AND `received_at <= as_of`, matching the precedent already set by
  `filter_pit_fundamentals()` and `RevisionStore.query_pit()`.
- **Unified composite formula** (`ca5a977`, proposal `dd29671`): `adjust()` gained an
  `algorithm_version` parameter — `"1.0"` legacy (default) / `"2.0"` unified.
  `_combined_dbr_factor()` implements `P_ex = (P_pre − D + Pr·R) / (1 + B + R)` for ex-date
  groups containing `RIGHTS_OFFERING` alongside `CASH_DIVIDEND` and/or `BONUS_ISSUE` — the only
  combination not already exactly equal to the independent-factor product. `STOCK_SPLIT` is
  explicitly out of scope (CEO-approved) and its branch is byte-for-byte unchanged.
  `ResearchInputManifest` gained trailing-defaulted `adjustment_algorithm_version` and it
  participates in `compute_input_hash()`.

## Completed — earlier
- **RIGHTS_OFFERING (配股)** (`c13955e`): the fourth corporate-action type, via the same
  single-reference-price substitution used by `CASH_DIVIDEND`.
- **Phase 9** — Research Result Persistence Hardening: `ResearchResultManifest` +
  `schema_version` and 8 trailing-defaulted scalar fields; atomic `ResearchRunStore.create_run()`;
  fail-closed `get_run()`; opt-in `verify_result_manifest_integrity()`;
  `research_application.py::get_research_run` reads canonical fields. See `docs/PHASE_9_REPORT.md`.
- **Phase 8R** — Certified Research Workbench UI + mandatory research-integrity enforcement.
- **Phase 8A** — Factor engine orchestration, certified replay integration.
- **Phase 7A–7J** — PIT temporal architecture, snapshot immutability, revision non-destructiveness,
  survivorship-bias-free universe, corporate-action binding, cross-provider reconciliation,
  persistent dataset certification.
- **Phase 2** — Context System Hardening & Multi-Agent Handoff Protocol.

## Not Implemented — honestly disclosed, not silently dropped
- **Research Report Identity + Persistence** — `ResearchAnalystReportIdentity` (design finalized
  in proposal §8) and its store are **not built**. This is §11 step 5, the next step in the plan.
- **Full Research Report** — the 10-section report of §7 (rendering, assembly, Data Confidence
  computation) is **not built**; `33296e7` stopped at validated structured output, per the
  directive's explicit scope boundary.
- **Streamlit UI** — §9, **not built**. Would require a new Application Layer module; only
  `streamlit_app.py` may import Streamlit.
- **Volatility / Momentum / Volume indicators** — `NotImplementedError` at
  `src/quant/technical/indicators.py:212,224,237`; design documented in each docstring.
- **Persistent `NewsAnnouncementStore`** — not built. News items are validated and PIT-filtered
  as in-memory lists returned by the adapter; there is no stateful, queryable, immutable
  revision store for news (contrast `CorporateActionStore`).
- **Real LLM API integration** — no vendor SDK (`openai` / `anthropic` / `google-generativeai`)
  is imported anywhere in `src/llm/`; `src/llm/` is not yet imported by anything outside itself
  and its tests.

## Currently In Progress
Nothing. Awaiting the next CEO directive.

## Tests
- **Passed**: 483
- **Skipped**: 11 (live-provider network tests, safely skipped when `TUSHARE_TOKEN` is absent)
- **Failures**: 0
- **Test Command**: `PYTHONPATH=. ./venv/bin/pytest`

## Git Status
- **Branch**: `main`
- **Working Tree**: Clean.
- **HEAD**: `33296e7` (`feat: LLM Provider interface layer (Evidence Bundle -> LLM Provider ->
  Validated Output)`)
- **Never pushed to remote without explicit Product Owner approval.**

## Known Issues
- **Live provider credentials**: TuShare Pro calls require `TUSHARE_TOKEN`. When absent, preflight
  skips live tests (`LIVE_PROVIDER_CREDENTIALS_UNAVAILABLE`) rather than fabricating data.
- **Unified adjustment formula is opt-in**: `adjustment_algorithm_version` defaults to `"1.0"`
  (legacy per-type independent factors). Existing certified runs are unaffected by design;
  `"2.0"` must be requested explicitly.
- **Numerical precision ceiling (disclosed, Phase 9)**: `ResearchRunStore.create_run()` rounds
  persisted floats to 6 decimals via `to_canonical_json` (pre-existing since Phase 7I). Harmless
  in practice — `BacktestEngine` already rounds to 4 decimals before `BacktestResult` is built.
- **AI prose is not bit-reproducible** — and is not claimed to be. Only `evidence_bundle_hash` and
  the deterministic `MODEL_OUTPUT` computations it covers are verifiable.
- **`.claude/DECISIONS.md` lines ~178–186 are now outdated**: they record the `received_at` PIT
  gap and the unified-formula reconciliation as open items. Both were closed by `e100cda` and
  `ca5a977`. Correcting `DECISIONS.md` was **not** authorized by the sync directive that produced
  this file — flagged here for a future documentation directive.
- **`docs/ROADMAP.md` is stale** (v1.0.0, `CEO-2026-08-01-REBUILD-001`): its 12-phase linear plan
  diverged from actual execution, and its "Phase 10/11/12" labels (Paper Trading / Broker / Live
  Trading) conflict with `CLAUDE.md`'s absolute scope boundary. Flagged for documentation
  governance; not actioned.
- **`turnover` / `trade_count` remain placeholders** in `BacktestEngine` (`turnover=0.15`
  hardcoded, `trade_count=len(daily_returns)`). A real fix requires multi-period rebalancing
  semantics design; explicitly not authorized.

## Important Files
- `CLAUDE.md` — Operating directive, context budget protocol, state machine, multi-agent protocol.
- `.claude/CURRENT_STATE.md` — This file: single-page active snapshot.
- `.claude/DECISIONS.md` — Permanent architectural memory (see Known Issues re: two stale entries).
- `.claude/HANDOFF.md` — Standardized multi-agent handoff contract.
- `AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md` — Current track's governing design (rev 2).
- `CORPORATE_ACTION_UNIFIED_FORMULA_ARCHITECTURE_PROPOSAL.md` — CEO-approved unified-formula design.
- `RIGHTS_OFFERING_ADJUSTMENT_ARCHITECTURE_PROPOSAL.md` — RIGHTS_OFFERING design (rev 2).
- `src/llm/` — LLM Provider interface layer (fully isolated; no vendor SDK).
- `src/quant/evidence/evidence_item.py` — Evidence Layer.
- `src/quant/technical/indicators.py` — MA/RSI/MACD implemented; 3 indicators still contract-only.
- `src/data/contracts/news_announcement.py`, `src/data/providers/news_provider.py` — news data path.
- `src/data/validation/pit_gate.py`, `src/data/revision/corporate_action_store.py` — dual-cutoff PIT.
- `src/quant/adjustment/corporate_action_adjuster.py` — all four action types + unified formula.
- `src/quant/reproducibility/` — canonical SHA-256 identity, manifests, replay, `ResearchRunStore`.
- `docs/PHASE_9_REPORT.md`, `docs/PHASE_8R_REPORT.md` — prior phase deliverable reports.
- `docs/CORPORATE_ACTION_SPECIFICATION.md`, `docs/FINAL_RESEARCH_INTEGRITY_CERTIFICATION.md`.

## Next Recommended Action
Await a CEO directive. The proposal's §11 step 5 — **`ResearchAnalystReportIdentity` +
persistence**, mirroring the existing `ResearchRunStore` pattern — is the recommended next unit
of work, but it is **not authorized** by any current document. Do NOT implement trading, broker
connections, or order routing. Do NOT create a "Phase 10."
