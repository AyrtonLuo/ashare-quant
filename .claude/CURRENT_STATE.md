# Current Project State

_Synchronized to HEAD `43dd721` (pushed to `origin/main`). Authority order per `CLAUDE.md` §2:
Actual Repository Code & Specs > Automated Test Suite > this file > Conversation History._

## Current Track
**AI Quant Terminal** — product repositioning from a quant research/audit system to a consumer
stock-analysis terminal, per the CEO Decision on
`AI_QUANT_TERMINAL_PRODUCT_SIMPLIFICATION_PROPOSAL.md` (`d4a2d70`). **Terminal is the default
mode; Research mode is retained unchanged.** Steps **T1, T2, T3, T3.5 and T5 are delivered — the Terminal serves REAL live quotes AND
computes all six technical indicators from REAL historical bars.** T4 (news) and T6 (real AI
narrative) remain vendor/credential-gated.

The preceding **AI Quant Research Analyst** track remains complete and untouched beneath it —
evidence-grounded LLM research synthesis.
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
Report → Application Layer → Streamlit UI`. **Two real LLM providers are wired** — Google
Gemini (`src/llm/gemini_provider.py`, the active default) and OpenAI
(`src/llm/openai_provider.py`), both over stdlib HTTP with **zero new dependencies**; the
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

- **Google Gemini LLM provider** (`94456ca`) — added *beside* OpenAI, now the active default.
  - **Nothing refactored**: `LLMProvider`, `LLMRequest`, `LLMResponse`, `LLMErrorCategory`,
    `StructuredResearchOutput`, `parse_structured_output()`, `validate_citations()`,
    `generate_ai_research_output()` and `openai_provider.py` are all **untouched**.
  - **Zero new dependencies**: official Gemini REST API via `urllib.request` + `json`; no
    `google-generativeai` SDK.
  - **Key hygiene**: `GEMINI_API_KEY` only; never on the instance, in an exception, in a log
    (AST-asserted), or in any persisted artifact. Missing key → `CREDENTIALS_UNAVAILABLE`
    *before* any socket. Auth travels in the **`x-goog-api-key` header, never `?key=`** — a
    secret in a URL leaks into proxy logs and history; a test asserts it never appears in the path.
  - **Evidence boundary at the wire level**: body built from `evidence_payload` only, with **no
    `tools`, no `functionDeclarations`, no `googleSearch`/grounding block**.
  - **Structured JSON output**: `responseMimeType` + `responseSchema` generated from the shipped
    structured-output constants (cannot drift), still re-validated by `parse_structured_output()`.
  - **Four real Gemini differences handled, not copied over**: model lives in the URL path; an
    **invalid key returns HTTP 400** (body's `error.status` inspected so a credential problem is
    not misreported as an outage); the schema dialect is uppercase and rejects
    `additionalProperties`; `candidatesTokenCount` may be omitted and is then **derived by
    subtraction** from reported counts — never a fabricated zero, and a negative derivation is
    malformed.
  - **Provider registry** in the app layer: `provider_id → (factory, env var, default model)`.
    Gemini is `DEFAULT_LLM_PROVIDER_ID`; **OpenAI is retained and selectable**; UI gains a
    provider selectbox. One vendor's missing credential **never** silently falls through to the
    other, and no provider failure is ever downgraded to a synthetic narrative.
  - 55 new tests, every offline one against a local 127.0.0.1 HTTP stub — **no test depends on
    the real API**.
- **Real OpenAI LLM provider** (`b00fe41`) — the first real vendor implementation, retained.
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
- **Real historical K-line + real-data technical indicators** (`43dd721`, step T3.5) — REAL mode
  now computes **all six** indicators from a real bar series, through
  API → Adapter → Contract → Validation → Application → Technical Indicators → UI.
  - **Audit finding**: `UnifiedDataProvider.fetch_market_data(symbol, trade_date)` returns ONE
    bar for ONE date — a 120-bar series would be 120 round-trips. A **series capability** was
    needed, not a new caller of the per-date one.
  - **Source chosen on measurement AND data quality**: Tencent `web.ifzq.gtimg.cn` **4/4,
    forward-adjusted** → chosen; Sina `getKLineData` **4/4 but UNADJUSTED** → rejected;
    East Money **3/4, dropped sockets** → rejected. Sina's rejection was **measured, not
    assumed**: 600519 has a corporate action inside the 120-day window (raw 1326.000 vs adjusted
    1297.976 on 2026-05-29), so raw prices would have produced visibly wrong MA/RSI/MACD.
  - The positional row layout `[date, open, close, high, low, volume]` was **verified across 105
    live distinct-price bars** (high==max, low==min) *before* the parser was written, and those
    invariants are **re-checked on every row at runtime** — a silent vendor reordering becomes a
    refusal, not wrong prices.
  - **New price basis `VENDOR_FORWARD_ADJUSTED`** (additive to `DerivedDataContract` +
    `DataTrustGate`): the series is adjusted for corporate actions but re-adjusted **as of
    today**, not point-in-time. **Correct for current indicators, wrong for backtesting.** The
    provider **declares its own basis**; the caller never guesses. Unreachable from any certified
    research path.
  - **Fail-closed, nothing substituted**: an unadjusted-only payload is **refused** rather than
    falling back to raw; transposed field order, unknown code, empty series, short row,
    non-numeric field, bad date, non-positive close, malformed JSON, HTTP error and unreachable
    host each raise; one incoherent bar refuses the **whole series** rather than being repaired
    or quietly dropped. Volume converted 手→shares (×100), vendor lot rounding (~0.001%) disclosed.
  - **REAL and DEMO run the identical computation path**, differing only in provider. **No
    REAL→DEMO fallback anywhere.** Every bar passes `DataTrustGate.validate_market_data` before
    reaching an indicator.
  - **Self-review caught a regression**: an initial blanket 34-bar gate made DEMO report 暂无数据
    for all six indicators when five were computable from its 25 bars. Availability is now decided
    **per indicator** — REAL 6/6 from 121 bars, DEMO 5/6 with MACD honestly short.
  - UI gains a **K 线历史** chart (closes, bar count, date range, source).
  - **VERIFIED**: live test ran (did not skip); browser showed 平安银行 11.56 +1.31% @ 10:46:03,
    a 121-bar chart (2026-03-02 → 2026-08-24) from `tencent_kline`, and MA 11.32 / RSI 55.26 /
    MACD 0.1151 / 量比 0.53 / 波动率 17.9% / 动量 +4.05% — all from real bars.
- **Real-time A-share quotes** (`3deffa5`, step T3) — **the Terminal shows REAL DATA by
  default**, through API → Adapter → Contract → Validation → Application → UI. No raw vendor
  data reaches the UI.
  - **Source chosen by measurement**: Sina `hq.sinajs.cn` **4/4** requests succeeded; Tencent
    **4/4**; East Money **2/4 — dropped sockets with no status code** (IP throttling), so it was
    rejected. Sina preferred over Tencent because it reports **volume in shares** (Tencent uses
    手/lots — a 100× error if assumed) and carries an explicit date/time. The 34-field layout was
    enumerated from a real response before the parser was written.
  - **Zero new dependencies** — `urllib.request` + GBK decoding, both stdlib. No key, no account,
    no purchase.
  - **⚠️ This is a public but UNDOCUMENTED, UNLICENSED endpoint.** No SLA, no support, no
    compatibility guarantee; quotes are delayed, not tick-level. Fine for research/personal use;
    **a licensed vendor is required before commercial distribution.** `LiveQuoteProvider` remains
    the licensed-vendor slot and still refuses explicitly.
  - **Fails closed, never substitutes**: a halted name (0.00) refuses rather than showing
    yesterday's close; an unknown code, truncated field layout, non-numeric price, unparseable
    timestamp, HTTP error or unreachable endpoint each raise. An unmappable symbol is refused,
    never guessed — guessing returns a real quote for the **wrong security**.
  - A 3-second cache keeps a page reload from becoming a burst against a free endpoint.
  - **REAL and DEMO are never mixed.** **There is no automatic REAL→DEMO fallback anywhere**:
    a failed fetch shows 暂无数据 + reason; a failed live search returns nothing rather than
    answering from the demo universe. (Technical indicators were 暂无数据 in REAL mode until
    T3.5 wired a real bar series; **fundamentals still are**, with the reason stated.)
  - UI: 数据源 selector (实时行情 default / 演示数据), **REAL DATA / DEMO DATA** badge on every
    card, plus 数据状态 / 数据更新时间 / 数据来源 / 交易状态. Search accepts a bare 6-digit code
    resolved live, so any listed A-share is reachable.
  - **REAL DATA VERIFIED**: the live test ran (did not skip) against the public endpoint, and the
    Terminal was confirmed in a browser showing REAL DATA with a same-minute timestamp during an
    open session.
- **Terminal mode — consumer stock view** (`a55d0ae`, step T2):
  - New `src/app/terminal_application.py`; the UI reaches project code only through Application
    Layer modules (now three), and this module imports no UI framework and **nothing from
    `src/llm/`**.
  - Panels: 搜索 → 行情 → AI 总结 → 技术面 → 基本面 → 新闻 → 风险 → 看多/看空.
  - **DEMO DATA badge is derived from `QuoteContract.data_origin`**, so a UI author cannot forget
    it and a golden quote can never present itself as live. Its 数据更新时间 is the demo bar's own
    historical timestamp, never `datetime.now()`.
  - **Missing data always says `暂无数据` with a reason, and every row stays in the table.**
    毛利率 reports "该指标尚未纳入当前数据契约，不做估算" — it genuinely is not a field on
    `FundamentalDataContract`. On the demo set only PE resolves; the other seven read 暂无数据.
    MACD honestly reads 暂无数据 (demo set has 25 bars; MACD needs 34).
  - **News returns empty + a reason, never a synthetic headline.**
  - Plain-language technical readings are **deterministic code, not a model**, and contain no
    买入/卖出/目标价 (both asserted by test).
  - Terminal branch of the UI is asserted to contain none of `evidence_bundle_hash`,
    `evidence_id`, `PIT`, `research_run_id`, `reproducibility_scope`, `result_hash`,
    `prompt_version` — the vocabulary is gone, the machinery is not.
  - Disclaimer 「本页面仅提供信息与分析，不构成投资建议。」 is persistent, not in an expander.
- **QuoteContract + QuoteProvider layer** (`2c6bc11`, step T1) — the one genuinely new data
  shape. `change`/`change_pct` are **computed properties, not stored fields**, so they cannot
  disagree with the prices shown beside them. `quoted_at` (vendor) and `received_at` (us) are
  distinct required facts. `GoldenQuoteProvider` is **structurally incapable** of claiming
  `REAL_PROVIDER` (hard-coded, not a parameter); `LiveQuoteProvider` **refuses explicitly** until
  a vendor is provisioned. `DataTrustGate.validate_quote()` checks internal coherence; staleness
  is opt-in only.
- **Realized volatility / momentum / volume indicators** (`5e3c701`, step T5) — the last three
  contract-only stubs are now real calculations implementing exactly their documented designs.
  Volume got its own validator (0 volume is valid for a suspended name; 0 price never is), an
  undefined ratio reports `None` rather than a fabricated 0.0/1.0, and split-adjustment is an
  explicit recorded flag. `DerivedDataContract` gained the `NOT_APPLICABLE` price basis, since
  volume is not a price.
- **Cloud deployment fix** (`5d1e998`) — `streamlit run` puts only the script's directory on
  `sys.path`, so `from src.app import ...` raised `ModuleNotFoundError` under the console script
  Streamlit Cloud uses. Reproduced in a bare clone, fixed by resolving the repo root from
  `__file__`. `.gitignore` now covers `.streamlit/secrets.toml`.
- **Product proposal** (`d4a2d70`) — `AI_QUANT_TERMINAL_PRODUCT_SIMPLIFICATION_PROPOSAL.md`,
  CEO-approved.
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
- **Persistent `NewsAnnouncementStore`** — not built. News items are validated and PIT-filtered
  as in-memory lists returned by the adapter; there is no stateful, queryable, immutable
  revision store for news (contrast `CorporateActionStore`).
- **Real Gemini end-to-end verification — NOT VERIFIED.** `GEMINI_API_KEY` is **not set** in
  this environment, so the real call could not be attempted at all. The test skips with a
  message stating plainly that it is *not* a verification. Its failure handling is deliberately
  narrow: only an exhausted account quota skips; a credential failure, rate limit, timeout or
  malformed response each **FAIL** with the exact classified `LLMErrorCategory`.
  **To complete it: set `GEMINI_API_KEY`, then run
  `PYTHONPATH=. ./venv/bin/pytest -m real_llm_provider`.**
- **Real OpenAI end-to-end verification — NOT COMPLETED.** The call reached OpenAI and
  **authenticated successfully**, then returned **HTTP 429 "You exceeded your current quota"** —
  an account billing condition, not a code defect. Same narrow-skip discipline. **To complete
  it: add OpenAI billing credit and re-run the same command.**

## Currently In Progress
Nothing. Awaiting the next CEO directive.

## Tests
- **Passed**: 895
- **Skipped**: 13 (11 TuShare live-provider tests when `TUSHARE_TOKEN` is absent; 1 real-OpenAI
  E2E blocked on account quota; 1 real-Gemini E2E blocked on an absent `GEMINI_API_KEY` — see
  Known Issues)
- **Failures**: 0
- **Test Command**: `PYTHONPATH=. ./venv/bin/pytest`

## Git Status
- **Branch**: `main`
- **Working Tree**: Clean.
- **HEAD**: `43dd721` (`feat: real historical K-line and real-data technical indicators
  (T3.5)`)
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
**Await CEO Review of T1/T2/T5.** All three Terminal steps that require nothing from the CEO are
delivered, tested and pushed. The remaining Terminal steps are gated on decisions only the CEO
can make:

- **T3 + T3.5 — DONE** (`3deffa5`, `43dd721`), via free public endpoints. Outstanding CEO
  decisions: (a) whether to procure a **licensed** feed before any commercial use — both current
  sources are unlicensed, undocumented and without SLA; (b) a **real fundamental source**, the
  last panel still reporting 暂无数据 in REAL mode.
- **T4 — real news provider**: blocked on a source decision. Nothing is wired.
- **T6 — real AI narrative**: blocked on an LLM credential/quota.

Also still outstanding, unchanged and credential-gated:

1. **Set `GEMINI_API_KEY`** (and/or add OpenAI billing credit), then run
   `PYTHONPATH=. ./venv/bin/pytest -m real_llm_provider` to complete the real end-to-end
   verification for whichever vendor is provisioned. Everything up to the vendor round-trip is
   already verified against local stubs for **both** providers, including a full 10-section
   report driven through each real provider class.
2. Optional, if wanted later: an Anthropic provider (the proposal's §8 examples name Claude).
   It would slot into `LLM_PROVIDER_REGISTRY` against the same ABC — no interface change — but
   needs `ANTHROPIC_API_KEY` and its own directive.
3. **Cloud deployment is code-ready but not deployed** — it needs the CEO's own Streamlit
   Community Cloud account authorization (main file `src/app/streamlit_app.py`, branch `main`,
   **Python 3.11 or 3.12 — not 3.13**, since `scipy==1.13.1`/`numpy==2.0.2` have no 3.13 wheels).
4. **`CLAUDE.md`'s Absolute Scope Boundary still says "Research/Backtest ONLY"** — the CEO
   deferred amending it until the Terminal architecture is finally confirmed. Flagged, not
   quietly stretched.

Do NOT implement trading, broker connections, or order routing. Do NOT create a "Phase 10."
