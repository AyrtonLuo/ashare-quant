# Current Project State

_Synchronized to HEAD `b00fe41` (pushed to `origin/main`). Authority order per `CLAUDE.md` §2:
Actual Repository Code & Specs > Automated Test Suite > this file > Conversation History._

## Current Track
**AI Quant Research Analyst** — evidence-grounded LLM research synthesis.
No phase number is assigned to this track (standing CEO instruction). **Phase 9 is complete.
Do NOT create a "Phase 10."**

Governing document: `AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md` (revision 2, repo root).
Its §11 Implementation Plan is the authoritative step list. **All six steps are delivered, plus
the §7 Research Report Generation Layer (which is not a numbered §11 step). The AI Research
Analyst track is feature-complete against the proposal as written.**

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
Output → Citation Validation → Report Identity → Immutable Persistence → 10-Section Research
Report → Application Layer → Streamlit UI`. **A real LLM provider is now wired**
(`src/llm/openai_provider.py`, OpenAI over stdlib HTTP, **zero new dependencies**); the
deterministic fakes are retained for testing and for the labelled-synthetic path.

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

- **Real OpenAI LLM provider** (`b00fe41`) — the first real vendor implementation.
  - **Zero new dependencies**: speaks the OpenAI Chat Completions HTTP API via
    `urllib.request` + `json`. `requirements.txt` unchanged; no vendor SDK imported anywhere in
    `src/`. CEO-approved choice (OpenAI was the only credential present; Anthropic/Gemini keys
    are unset).
  - **`LLMProvider` interface required no change**, and neither did the proposal — a real
    provider was always meant to be a drop-in for the fakes, and this commit proves it.
  - **Key hygiene**: read from the environment only (no constructor arg, attribute, or config
    file can carry it), never stored on the instance, never in an exception message, never
    logged (the module performs no logging). Missing key → `CREDENTIALS_UNAVAILABLE` *before*
    any socket opens.
  - **Evidence Boundary at the wire level**: request body built from `evidence_payload` only,
    with **no tools / function calling / retrieval option** — the model has no capability to
    reach a database, news API, or the network from inside the call.
  - **Schema-enforced structured output**: `response_format` pins a strict JSON schema
    generated from the shipped `REQUIRED_STRUCTURED_OUTPUT_FIELDS` constants (cannot drift), and
    the response still passes through `parse_structured_output()` — transport guarantees are
    never a substitute for validation.
  - **Every failure maps to exactly one `LLMErrorCategory`** (401/403 auth, 429 rate limit,
    408/504 + socket timeout, 5xx/connection unavailable, non-JSON/non-object/truncated
    malformed, no-choices/blank empty, refusal invalid). A missing `usage` block is malformed,
    never back-filled with zeros.
  - **Provenance**: `data_origin="REAL_PROVIDER"` is set here and only here; the fakes hard-code
    `SYNTHETIC_DATA`, so **a fake can never impersonate a real provider** in a persisted artifact.
  - App layer + UI updated: `LLM_PROVIDER_AVAILABLE` / `LLM_PROVIDER_CREDENTIALS_UNAVAILABLE`
    replace the now-false `NO_LIVE_LLM_PROVIDER_IMPLEMENTED`; the real provider is used when a
    credential is present and **fails closed when it is not — never silently downgraded to a
    synthetic narrative**. UI gains an explicit narrative-source choice.
  - 41 new tests (offline, against a local 127.0.0.1 HTTP stub — deterministic, free,
    network-free). All existing Fake Provider tests retained unchanged.
- **Streamlit UI + analyst Application Layer** (`aebef90`, §9 / §11 step 6):
  - `src/app/research_analyst_application.py` (new) mirrors `research_application.py`'s
    contract — the UI calls only this module; this module imports no UI framework. It assembles
    Evidence from the certified GOLDEN_DATASET (MARKET + FUNDAMENTAL via existing assembly
    functions, TECHNICAL by calling the **shipped** MA/RSI/MACD — no new indicator), PIT by
    construction, with `input_price_basis="RAW"` declared honestly since the golden closes are
    unadjusted.
  - **Availability is reported, never faked**: the workbench dataset has no news feed and no
    factor/risk evidence assembly, so `NEWS` / `QUANT_FACTOR` / `RISK` return NOT AVAILABLE each
    with its own reason string, and the report layer renders those sections as NOT AVAILABLE.
  - `get_llm_provider_status()` reports **`NO_LIVE_LLM_PROVIDER_IMPLEMENTED`** — the honest
    blocker. Credential preflight is surfaced but a present key never upgrades the status (there
    is no vendor client to use it with), and no key value is ever exposed.
  - `generate_analyst_report()` **fails closed by default**. A caller may opt in to a
    clearly-labelled synthetic narrative: real certified Evidence + fixed placeholder prose
    authored in the app layer (not by any model) that says "SYNTHETIC PLACEHOLDER — not
    analysis, no LLM was called" in every section and **contains no numerals at all**, tagged
    `data_origin="SYNTHETIC_DATA"` on the persisted identity. Mirrors the existing
    `LiveNewsAnnouncementProvider` (explicit refusal) / `SyntheticNewsAnnouncementProvider`
    (labelled fixtures) convention. **Awaiting CEO confirmation of this design choice.**
  - `streamlit_app.py` gains an "AI Research Analyst" page: provider banner, symbol/as_of
    selectors, Evidence Bundle panel (per-category AVAILABLE/NOT AVAILABLE + reasons, origin
    breakdown, bundle hash, item expander), computed Data Confidence panel, conflicts table,
    all 10 sections with content-type badges and per-section evidence ids, withheld narrative in
    an expander, provenance incl. `reproducibility_scope`, disclaimer, limitations, Markdown
    download. Generation sits behind an opt-in checkbox that is **off by default**.
  - `golden_dataset_seed.py`: one additive public `market_data()` accessor (no second
    contract-construction site that could drift).
  - `test_phase_8r_security_boundary.py`: the UI-import assertion became an **allow-list of
    Application Layer entry points** (§9 specifies the analyst page gets its own module).
    `FORBIDDEN_UI_IMPORTS` is unchanged — every research internal still fails. Not a relaxation.
  - 35 new tests.
- **Research Report Generation Layer** (`0795400`, proposal §7 — `data_confidence.py` and
  `report.py` added to `src/quant/research_report/`, **zero existing files modified**):
  - **Schema fit, audited not assumed**: §7's 10 sections map onto the shipped
    `StructuredResearchOutput` without changing it — its 9 narrative fields are §7's 9 AI
    sections, and §7 #9 (Data Confidence) is Model Output only, computed here. **The LLM
    contract was not modified.**
  - `data_confidence.py` — `detect_evidence_conflicts()` (deterministic; surfaces disagreement,
    never resolves it; keys defined only for `MARKET`/`FUNDAMENTAL`/`TECHNICAL`, the categories
    with an actually-implemented content schema) and `compute_data_confidence()` (sub-scores:
    origin / coverage / recency / conflict, explicit renormalized weights, every component
    exposed so the score is re-derivable by hand; `computed_by="DETERMINISTIC_CODE"`; this
    module imports nothing from `src/llm/`). Fails closed on an empty bundle.
  - `report.py` — `ResearchReport` / `ReportSection` with all 10 sections tagged
    `FACT` / `MODEL_OUTPUT` / `AI_INTERPRETATION`; **no verdict/rating/recommendation/signal
    field exists**, so a single Buy/Sell conclusion has nowhere to live; identical Bull/Bear
    fails closed; absent categories render an explicit `NOT AVAILABLE` marker with the AI's
    prose retained on `suppressed_ai_body`; §7 #8 carries a code-generated deterministic risk
    addendum listing unresolved conflicts and missing categories; `render_report_markdown()` is
    framework-free. `derive_section_evidence_ids()` reuses the citation validator's own numeric
    tracing rather than declaring a second scanner.
  - **Disclosed on the artifact itself** (`REPORT_LIMITATIONS`): AI prose is not
    bit-reproducible; citation validation is not semantic fact-checking; the conflict-detection
    scope excludes semantic contradiction between free-text news; per-section attribution is
    *derived*, not model-asserted; and category-level `historical_eligible` (§3.4) is **not
    implemented anywhere in this codebase**.
  - 57 new tests.
- **Research Report Identity + Persistence** (`43b692a`, §11 step 5 — new isolated package
  `src/quant/research_report/`, **zero existing files modified**):
  - `report_identity.py` — `ResearchAnalystReportIdentity`: all 11 fields of proposal §8, plus
    trailing-defaulted provider provenance (`provider_id`, `provider_version`, `model`,
    `llm_request_id`, `data_origin`, `schema_version`, `reproducibility_scope`). Fail-closed on
    empty required strings and on an empty-string `research_run_id`/`data_snapshot_id` (`None`
    means genuinely absent; `""` would be a fabricated link).
    `build_research_analyst_report_identity()` copies provenance from the validated
    `AIResearchOutputResult`; an unreported `model_version` is recorded as
    `NOT_REPORTED_BY_PROVIDER`, never invented. `get_code_version()` reused verbatim.
    `verify_report_evidence_integrity()` is opt-in, mirroring `verify_result_manifest_integrity()`.
  - `report_store.py` — `ResearchAnalystReportStore` under `data/research/analyst_reports/`
    (gitignored): immutable, atomic tmp-then-rename writes, fail-closed corruption handling,
    persisting `report_metadata.json` / `structured_output.json` / `evidence_bundle.json`. The
    bundle is stored deliberately — without it `evidence_bundle_hash` would be unverifiable.
    `create_report()` refuses a self-inconsistent pair: mismatched hash, empty bundle, or an
    output citing an `evidence_id` absent from the bundle.
  - **Honest reproducibility scope, enforced structurally**: the identity carries **no
    `result_hash`** and no hash of any kind over the narrative;
    `reproducibility_scope` is a validated, persisted field
    (`EVIDENCE_BUNDLE_DETERMINISTICALLY_VERIFIABLE; AI_PROSE_NOT_BIT_REPRODUCIBLE`) that
    `__post_init__` refuses to let a caller override with a stronger claim. Two reports over
    identical evidence with different wording share one `evidence_bundle_hash` and both verify.
  - 42 new tests.

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
- **Volatility / Momentum / Volume indicators** — `NotImplementedError` at
  `src/quant/technical/indicators.py:212,224,237`; design documented in each docstring.
- **Persistent `NewsAnnouncementStore`** — not built. News items are validated and PIT-filtered
  as in-memory lists returned by the adapter; there is no stateful, queryable, immutable
  revision store for news (contrast `CorporateActionStore`).
- **Real end-to-end API verification — NOT COMPLETED.** The real call reached OpenAI and
  **authenticated successfully**, then returned **HTTP 429 "You exceeded your current quota"**.
  That is an account billing condition, not a code defect. The live test skips on exactly that
  condition with a message stating it is *not* a verification; the skip is deliberately narrow —
  auth failures, timeouts, malformed responses and ordinary rate limits all still fail loudly.
  **To complete it: add billing credit to the OpenAI account, then run
  `PYTHONPATH=. ./venv/bin/pytest -m real_llm_provider`.**

## Currently In Progress
Nothing. Awaiting the next CEO directive.

## Tests
- **Passed**: 660
- **Skipped**: 12 (11 TuShare live-provider tests when `TUSHARE_TOKEN` is absent; 1 real-LLM
  end-to-end test blocked on OpenAI account quota — see Known Issues)
- **Failures**: 0
- **Test Command**: `PYTHONPATH=. ./venv/bin/pytest`

## Git Status
- **Branch**: `main`
- **Working Tree**: Clean.
- **HEAD**: `b00fe41` (`feat: real OpenAI LLM provider over stdlib HTTP (zero new
  dependencies)`)
- **`origin/main` is in sync with local `main`.** Pushes are made only under an explicit CEO
  directive authorizing them (as with Step 5 and the §7 layer).
- Standing rule unchanged: **never push without explicit Product Owner approval.**

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
Await a CEO directive. **The AI Research Analyst track is complete end to end, including a real
LLM provider.** One item is outstanding and is the CEO's to unblock:

1. **Add billing credit to the OpenAI account and re-run
   `PYTHONPATH=. ./venv/bin/pytest -m real_llm_provider`** to complete the real end-to-end
   verification. Everything up to the vendor round-trip is already verified against a local
   stub, including a full 10-section report driven through the real provider class.
2. Optional, if wanted later: an Anthropic provider (the proposal's §8 examples name Claude).
   It would implement the same ABC alongside `OpenAILLMProvider` — no interface change — but
   needs `ANTHROPIC_API_KEY` and its own directive.

Do NOT implement trading, broker connections, or order routing. Do NOT create a "Phase 10."
