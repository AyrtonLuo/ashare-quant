# Agent Handoff

_Synchronized to HEAD `4c1c8dd` (pushed to `origin/main`). Authority order per `CLAUDE.md` §2:
Actual Repository Code & Specs > Automated Test Suite > `.claude/` files > Conversation History._

## Handoff Status
READY

## Current Track
**AI Quant Terminal** — consumer repositioning per the CEO Decision on
`AI_QUANT_TERMINAL_PRODUCT_SIMPLIFICATION_PROPOSAL.md` (`d4a2d70`). **Terminal is the default
mode, Research mode is retained unchanged.** **Every data panel now runs on REAL data** — live quotes, all six technical indicators from REAL
historical bars, REAL valuation fundamentals, and REAL company announcements. Only the **AI
narrative** remains credential-gated.

The prior **AI Quant Research Analyst** track sits complete beneath it — no phase number assigned
(standing CEO instruction).
**Phase 9 is complete. Do NOT create a "Phase 10."**

Governing document: `AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md` (revision 2, repo root),
§11 Implementation Plan. **All six steps delivered, plus the §7 Research Report Generation
Layer (not a numbered §11 step). The track is feature-complete against the proposal as
written.**

## Current Objective
None in flight. Terminal steps **T5 (`5e3c701`), T1 (`2c6bc11`), T2 (`a55d0ae`) and T3
(`3deffa5`)** are delivered, tested and pushed, plus **T3.5 (`43dd721`)**, **T4 (`7e9258f`)** and **T5
(`4c1c8dd`)**. **Quotes, K-line history, valuation fundamentals and company announcements are all
live and verified against public endpoints.** **STOP — await CEO Review.**

## Completed
- **Real company announcements** (`4c1c8dd`, T5) — `eastmoney_news_provider.py`, implementing the
  `NewsAnnouncementProvider` ABC that already shipped. Stdlib-only, **zero new dependencies**, and
  **no news contract / validation / PIT code was changed**. Sources measured: East Money **3/3
  then 4/4 on four codes, 1 call** → chosen; **cninfo (the OFFICIAL platform) rejected** because
  its `orgId` is **not derivable** and a wrong one returns `total: 0` **silently with HTTP 200** —
  which would render as 「暂无新闻」 when the lookup was simply wrong. Nothing invented:
  `body_summary` stays **empty** (no body text exists; every item links to the original document),
  symbol association comes from the payload's own `codes[]`, `relevance_score` is a deterministic
  rule, and `item_type` is always `COMPANY_ANNOUNCEMENT`. DEMO mode has **no** news source and
  says so; a REAL failure never becomes a DEMO answer. 35 tests.
- **Real fundamental / valuation data** (`7e9258f`, T4) — `fundamental_provider.py` (ABC + demo)
  and `tencent_fundamental_provider.py` (real), stdlib-only, **zero new dependencies**. A THIRD
  capability: quotes, history and fundamentals each declare their **own** provider and
  `source_label`. Sources measured: Tencent **3/3** chosen; **East Money 0/3, every socket
  dropped** (degraded 2/4 → 3/4 → 0/3 across T3/T3.5/T4). Every field cross-validated against an
  independent Sina derivation on **3 symbols including a dual-listed one**: the market-cap
  identity and the vendor PE both matched **exactly 3/3**, and field **[73] = TOTAL share
  capital** was discriminated from 流通股本 by 000333. **PB is vendor-reported, never derived** —
  a derived PB was wrong for 000333 (2.800 vs 3.19). 营收/净利润/毛利率/净利率/EPS/ROE stay `None`
  → 暂无数据 with a reason. Market-cap identity re-checked on every fetch. 43 tests.
- **Real historical K-line + real technical indicators** (`43dd721`, T3.5) —
  `history_provider.py` (ABC + demo) and `tencent_history_provider.py` (real), stdlib-only,
  **zero new dependencies**. A **series** capability was needed because
  `fetch_market_data(symbol, trade_date)` returns one bar per call. Source chosen on measurement
  **and data quality**: Tencent 4/4 **forward-adjusted** → chosen; Sina 4/4 but **unadjusted** →
  rejected because 600519 has a corporate action in the window (raw 1326.000 vs adjusted
  1297.976) that would visibly distort MA/RSI/MACD; East Money 3/4 dropped → rejected. The
  positional layout was **verified across 105 live bars before the parser was written** and its
  invariants re-checked per row. New `VENDOR_FORWARD_ADJUSTED` basis (adjusted, but as-of-today,
  **not** PIT — correct for display, **wrong for backtesting**), declared by the provider. Every
  bar passes `DataTrustGate.validate_market_data`. **REAL 6/6 indicators from 121 bars; DEMO 5/6
  with MACD honestly short.** 31 tests.
- **Real-time A-share quotes** (`3deffa5`, T3) — `src/data/providers/sina_quote_provider.py`,
  stdlib-only (`urllib` + GBK), **zero new dependencies**, no key/account/purchase. Source picked
  by live measurement: Sina 4/4, Tencent 4/4, **East Money 2/4 (dropped sockets, IP throttling)
  → rejected**. Sina preferred because it reports volume in **shares** (Tencent uses 手 — a 100×
  error if assumed). `data_origin="REAL_PROVIDER"` only from a parsed live response; a halted
  name, unknown code, truncated layout, non-numeric price, bad timestamp, HTTP error or
  unreachable host each **fail closed** — nothing is ever substituted, and an unmappable symbol
  is refused rather than guessed. 3-second cache. **REAL DATA verified live.**
- **Terminal mode — consumer stock view** (`a55d0ae`, T2) — `src/app/terminal_application.py`
  plus a Terminal-default 模式 switch in the UI. Panels: 搜索 → 行情 → AI 总结 → 技术面 → 基本面 →
  新闻 → 风险 → 看多/看空. The DEMO DATA badge derives from `QuoteContract.data_origin`; missing
  data always says `暂无数据` **with a reason** and the row is never dropped; news returns empty
  plus its reason and never a synthetic headline; the plain-language readings are deterministic
  code containing no 买入/卖出/目标价. The Terminal branch of the UI contains none of
  `evidence_bundle_hash` / `evidence_id` / `PIT` / `research_run_id` / `reproducibility_scope` /
  `result_hash` / `prompt_version`. Disclaimer is persistent. 34 tests.
- **QuoteContract + QuoteProvider** (`2c6bc11`, T1) — the new "price right now" shape the PIT
  path never had. `change`/`change_pct` are computed properties, not stored fields.
  `GoldenQuoteProvider` cannot claim `REAL_PROVIDER` (hard-coded); `LiveQuoteProvider` refuses
  explicitly. `DataTrustGate.validate_quote()` added; staleness opt-in only. 45 tests.
- **Volatility / momentum / volume indicators** (`5e3c701`, T5) — the last three stubs are real
  calculations. Volume has its own validator, an undefined ratio is `None` not a fabricated
  number, split-adjustment is an explicit flag, and `DerivedDataContract` gained the
  `NOT_APPLICABLE` price basis. 30 tests.
- **Cloud deployment fix** (`5d1e998`) — the app could not have started on Streamlit Cloud
  (`ModuleNotFoundError: No module named 'src'` under the console-script launcher). Reproduced in
  a bare clone and fixed via a `__file__`-derived repo root. `.streamlit/secrets.toml` gitignored.
- **Product proposal** (`d4a2d70`) — CEO-approved.
- **Google Gemini LLM provider** (`94456ca`) — `src/llm/gemini_provider.py`, added **beside**
  OpenAI and now the active default. **Nothing was refactored**: the ABC, `LLMRequest`,
  `LLMResponse`, `LLMErrorCategory`, `StructuredResearchOutput`, the citation validator, the
  analyst orchestration and `openai_provider.py` are all untouched. Official Gemini REST API via
  `urllib.request` + `json`; **no `google-generativeai` SDK, `requirements.txt` unchanged**.
  `GEMINI_API_KEY` from the environment only — never on the instance, in an exception, in a log
  (AST-asserted), or in any persisted artifact; missing key → `CREDENTIALS_UNAVAILABLE` before
  any socket. Auth in the **`x-goog-api-key` header, never `?key=`**. No `tools` /
  `functionDeclarations` / `googleSearch` grounding in the body, so the Evidence Boundary holds
  at the wire level. `responseMimeType` + `responseSchema` generated from the shipped
  structured-output constants, still re-validated upstream. Gemini-specific handling: model in
  the URL path, **HTTP 400 `API_KEY_INVALID` mapped to `AUTHENTICATION_FAILURE`** (not a generic
  outage), uppercase schema dialect, and an omitted `candidatesTokenCount` **derived by
  subtraction** rather than zero-filled. App-layer `LLM_PROVIDER_REGISTRY` makes both providers
  selectable with Gemini as `DEFAULT_LLM_PROVIDER_ID`; the UI gains a provider selectbox. 55 new
  tests, all offline against a local HTTP stub.
- **Real OpenAI LLM provider** (`b00fe41`) — retained, unchanged, still selectable. — `src/llm/openai_provider.py`, the first real vendor
  implementation, speaking the OpenAI Chat Completions HTTP API through `urllib.request` +
  `json`. **Zero new dependencies** (`requirements.txt` unchanged; no vendor SDK anywhere in
  `src/`). **The `LLMProvider` ABC and the proposal both needed no change.** API key read from
  the environment only — never on the instance, never in an exception, never logged; missing key
  raises `CREDENTIALS_UNAVAILABLE` before any socket opens. No tools / function calling /
  retrieval in the request body, so the Evidence Boundary holds at the wire level. Strict JSON
  schema built from the shipped structured-output constants (cannot drift), still re-validated
  by `parse_structured_output()`. Every failure maps to exactly one `LLMErrorCategory`; a
  missing `usage` block is malformed, never zero-filled. `data_origin="REAL_PROVIDER"` is set
  here and only here. App layer + UI updated to report
  `LLM_PROVIDER_AVAILABLE` / `LLM_PROVIDER_CREDENTIALS_UNAVAILABLE` and to use the real provider
  when a credential exists. 41 new tests against a local HTTP stub; all Fake Provider tests
  retained.
- **Streamlit UI + analyst Application Layer** (`aebef90`, §9 / §11 step 6) — new
  `src/app/research_analyst_application.py` (the UI calls only it; it imports no UI framework);
  an "AI Research Analyst" page in `streamlit_app.py` rendering the Evidence Bundle with
  per-category AVAILABLE / NOT AVAILABLE + reasons and origin breakdown, the computed Data
  Confidence panel, the conflicts table, all 10 sections with content-type badges and
  per-section evidence ids, withheld narrative in an expander, provenance incl.
  `reproducibility_scope`, disclaimer, limitations and a Markdown download. Evidence is
  assembled from the certified GOLDEN_DATASET (MARKET + FUNDAMENTAL via existing assembly
  functions, TECHNICAL by calling the **shipped** MA/RSI/MACD — no new indicator), PIT by
  construction, `input_price_basis="RAW"` declared honestly. `get_llm_provider_status()` reports
  **`NO_LIVE_LLM_PROVIDER_IMPLEMENTED`**; `generate_analyst_report()` **fails closed by
  default**, with an opt-in, unmistakably-labelled `SYNTHETIC_DATA` placeholder narrative
  (no numerals, authored in the app layer, never by a model). One additive `market_data()`
  accessor on `golden_dataset_seed.py`. 35 new tests.
- **Research Report Generation Layer** (`0795400`, proposal §7) — `data_confidence.py` +
  `report.py`, both new, zero existing files modified. **§7's 10 sections fit the shipped
  `StructuredResearchOutput` without changing it**: its 9 narrative fields are §7's 9 AI
  sections, and §7 #9 Data Confidence is Model Output computed by code — so the LLM contract was
  audited and left untouched. `ResearchReport`/`ReportSection` tag every section
  `FACT`/`MODEL_OUTPUT`/`AI_INTERPRETATION`; there is **no verdict/rating/recommendation/signal
  field**, so a single Buy/Sell conclusion has nowhere to live; identical Bull/Bear fails
  closed; an absent evidence category renders `NOT AVAILABLE` with the AI prose retained on
  `suppressed_ai_body`; §7 #8 carries a code-generated risk addendum naming unresolved conflicts
  and missing categories. `detect_evidence_conflicts()` surfaces disagreement and never resolves
  it; `compute_data_confidence()` is `DETERMINISTIC_CODE` with every sub-score exposed and
  imports nothing from `src/llm/`. `derive_section_evidence_ids()` reuses the citation
  validator's own numeric tracing. `render_report_markdown()` is framework-free. 57 new tests.
- **Research Report Identity + Persistence** (`43b692a`, §11 step 5) — new isolated package
  `src/quant/research_report/`, every file new, zero existing files modified.
  `report_identity.py`: `ResearchAnalystReportIdentity` (all 11 proposal-§8 fields + trailing-
  defaulted provider provenance: `provider_id`, `provider_version`, `model`, `llm_request_id`,
  `data_origin`, `schema_version`, `reproducibility_scope`), fail-closed `__post_init__`,
  `build_research_analyst_report_identity()` (provenance copied from the validated
  `AIResearchOutputResult`; an unreported `model_version` becomes `NOT_REPORTED_BY_PROVIDER`,
  never invented), `get_code_version()` reused verbatim, `serialize_evidence_bundle_payload()`
  delegating to the existing projection so it cannot drift from the hash, and opt-in
  `verify_report_evidence_integrity()`. `report_store.py`: `ResearchAnalystReportStore` —
  immutable, atomic tmp-then-rename, fail-closed corruption handling, three persisted artifacts
  (`report_metadata.json` / `structured_output.json` / `evidence_bundle.json`), and four
  fail-closed write guards (duplicate id, empty bundle, hash/bundle mismatch, dangling
  citation). **The identity carries no `result_hash` and no hash over the prose**;
  `reproducibility_scope` is a validated persisted field that cannot be overridden with a
  stronger claim. 42 new tests.
- **LLM Provider interface layer** (`33296e7`) — new package `src/llm/`, every file new, zero
  existing files modified. Delivers `Evidence Bundle → LLM Provider → Structured Output →
  Deterministic Citation Validator`:
  `provider_base.py` (`LLMProvider` ABC, `LLMRequest`/`LLMResponse`/`LLMTokenUsage`,
  8-category `LLMErrorCategory` + `LLMProviderError`), `structured_output.py`
  (`StructuredResearchOutput` 10-field schema, fail-closed `parse_structured_output()`),
  `citation_validator.py` (`validate_citations()` — deterministic code, not a second LLM call),
  `credential.py` (`LLMProviderCredentialPreflight`, generic over provider/env-var name),
  `fake_provider.py` (`FakeLLMProvider` + `AlternateFakeLLMProvider`, proving provider switching),
  `research_analyst.py` (`generate_ai_research_output()` — the single call site;
  `AIResearchIdentity`). 49 new tests. **No vendor SDK is imported anywhere in `src/llm/`; no
  live LLM API call exists in this codebase.**
- **AI Research Analyst data infrastructure** (`f75b0ef`) — `NewsAnnouncementContract`,
  `NewsAnnouncementProvider` ABC + synthetic/explicit-refusal implementations, `DataTrustGate`
  news/technical validators, `PITGate.filter_pit_news_announcements()`, Evidence Layer
  (`EvidenceItem`, assembly functions, duplicate detection, bundle hashing), and MA/RSI/MACD.
  Proposal synced to the implemented shape in `436cb61`.
- **Corporate action unified formula** (`ca5a977`, proposal `dd29671`) — `adjust()` gained
  `algorithm_version` (`"1.0"` legacy default / `"2.0"` unified); `_combined_dbr_factor()`
  implements `P_ex = (P_pre − D + Pr·R) / (1 + B + R)`. `STOCK_SPLIT` explicitly out of scope
  (CEO-approved), branch byte-for-byte unchanged. `ResearchInputManifest` gained trailing-
  defaulted `adjustment_algorithm_version`, participating in `compute_input_hash()`.
- **Corporate action `received_at` PIT enforcement** (`e100cda`) — both
  `PITGate.filter_pit_corporate_actions()` and `CorporateActionStore.query_pit()` /
  `query_pit_range()` now require `available_at <= as_of` AND `received_at <= as_of`.
- **RIGHTS_OFFERING (配股)** (`c13955e`) — fourth corporate-action type.
- **Phase 9** — Research Result Persistence Hardening (`docs/PHASE_9_REPORT.md`).
- **Phase 1 – 8R** — certified research workbench, PIT dual-cutoff isolation, factor orchestration.
- **Phase 2** — Context System Hardening (`CLAUDE.md` budget protocol, state machine, role map).

## Not Completed — disclosed, not silently dropped
1. **Real Gemini end-to-end verification — NOT VERIFIED (no credential).** `GEMINI_API_KEY` is
   not set here, so the real call was never attempted. The test skips saying plainly it is not a
   verification. Its failure handling is **deliberately narrow**: only an exhausted account quota
   skips; a credential failure, rate limit, timeout or malformed response each **FAIL** with the
   exact classified `LLMErrorCategory`, never softened into a pass. **To finish: set
   `GEMINI_API_KEY`, then run `PYTHONPATH=. ./venv/bin/pytest -m real_llm_provider`.**
2. **Real OpenAI end-to-end verification — NOT COMPLETED (account quota).** The call
   authenticated, then returned HTTP 429 "exceeded your current quota". Not a code defect. Same
   narrow-skip discipline. **To finish: add OpenAI billing credit and re-run the same command.**
   For both providers, everything short of the vendor round-trip is already verified against a
   local stub, including a full 10-section report driven through each real provider class.
3. **An Anthropic provider** — the proposal's §8 examples name Claude, and `ANTHROPIC_API_KEY`
   is unset here. It would slot into `LLM_PROVIDER_REGISTRY` against the same ABC with no
   interface change, but needs its own directive.
4. **Persistent `NewsAnnouncementStore`** — news is validated/PIT-filtered in memory only; no
   stateful immutable revision store exists for news.
5. **Category-level `historical_eligible` (§3.4)** — never implemented anywhere. The report
   marks an absent category as `NOT AVAILABLE` without distinguishing "structurally
   current-only" from "simply absent". Disclosed in `REPORT_LIMITATIONS` on every report.
6. **Semantic conflict detection between free-text news items** (§3.3's "M&A rumour later
   denied") — not deterministically decidable, so not claimed. `CONFLICT_DETECTION_SCOPE` is
   carried onto every report so "no conflicts detected" cannot be misread as "no conflicts
   exist"; surfacing that class remains the AI's narrative contract (§6).

## Current Test Baseline
- **Passed**: 974
- **Skipped**: 13 (11 TuShare live-provider tests; 1 real-Gemini E2E with no credential; 1
  real-OpenAI E2E blocked on account quota — items 1 and 2 under Not Completed)
- **Failures**: 0
- **Test Command**: `PYTHONPATH=. ./venv/bin/pytest`

## Git Status
- **Branch**: `main`; **Working Tree**: clean; **HEAD**: `4c1c8dd`.
- **`origin/main` is in sync with local `main`** (pushed under explicit CEO authorization for
  this directive).
- Standing rule unchanged: never push without explicit Product Owner approval.

## Relevant Files
- `CLAUDE.md` — Operating directive, context budget protocol, state machine, multi-agent protocol.
- `.claude/CURRENT_STATE.md` — Single-page active snapshot (state, tests, git, known issues).
- `.claude/DECISIONS.md` — Permanent architectural memory. **Two entries are stale** — see below.
- `AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md` — Current track's governing design (rev 2);
  §1a status table, §1b next-phase diagram, §6–§9 design-only sections, §11 plan.
- `CORPORATE_ACTION_UNIFIED_FORMULA_ARCHITECTURE_PROPOSAL.md`,
  `RIGHTS_OFFERING_ADJUSTMENT_ARCHITECTURE_PROPOSAL.md` — CEO-approved corporate-action designs.
- `src/llm/` — LLM Provider layer. `gemini_provider.py` (default) and `openai_provider.py` are
  the real, network-calling implementations (stdlib HTTP, no vendor SDK); `fake_provider.py`
  holds the deterministic doubles.
- `src/quant/research_report/report_identity.py`, `report_store.py` — Step 5 identity + store.
- `src/quant/research_report/report.py`, `data_confidence.py` — §7 report generation +
  computed Data Confidence / conflict detection.
- `src/app/research_analyst_application.py` — analyst Application Layer.
- `src/app/terminal_application.py` — Terminal Application Layer (the ONLY module the Terminal
  page may call into). Imports nothing from `src/llm/`.
- `src/data/contracts/quote.py`, `src/data/providers/quote_provider.py` — the T1 quote layer.
- `src/data/providers/sina_quote_provider.py` — the REAL live quote source (T3).
- `src/data/providers/history_provider.py`, `tencent_history_provider.py` — the REAL daily K-line
  series feeding the technical panel (T3.5).
- `src/data/providers/fundamental_provider.py`, `tencent_fundamental_provider.py` — the REAL
  valuation source feeding the fundamental panel (T4).
- `src/data/providers/eastmoney_news_provider.py` — the REAL announcement source feeding the
  最新消息 panel (T5).
- `AI_QUANT_TERMINAL_PRODUCT_SIMPLIFICATION_PROPOSAL.md` — the approved Terminal design.
- `src/app/streamlit_app.py` — the ONLY file permitted to import Streamlit.
- `src/quant/evidence/evidence_item.py`, `src/quant/technical/indicators.py` — Evidence + indicators.
- `src/data/validation/pit_gate.py`, `src/data/revision/corporate_action_store.py` — dual-cutoff PIT.
- `src/quant/adjustment/corporate_action_adjuster.py` — four action types + unified formula.
- `docs/PHASE_9_REPORT.md`, `docs/PHASE_8R_REPORT.md`, `docs/CORPORATE_ACTION_SPECIFICATION.md`.

## Important Decisions
- **PIT is now uniformly dual-cutoff**: corporate actions match fundamentals and revisions —
  `available_at <= as_of` AND `received_at <= as_of`, enforced at both the store and the gate.
  The asymmetry previously documented here no longer exists in code (`e100cda`).
- **Unified adjustment formula is opt-in**: `adjustment_algorithm_version` defaults to `"1.0"`,
  so existing certified runs and their hashes are unaffected. `"2.0"` must be requested
  explicitly, and the choice is itself certified via `compute_input_hash()`.
- **AI prose is not claimed to be bit-reproducible.** Only `evidence_bundle_hash` and the
  deterministic `MODEL_OUTPUT` computations it covers are verifiable. This is no longer only a
  convention: `ResearchAnalystReportIdentity` has no `result_hash`, and its
  `reproducibility_scope` field is validated in `__post_init__`, so a caller cannot persist a
  stronger claim. Do not add one.
- **Terminal is the default mode; Research mode must stay reachable and unchanged.**
- **REAL and DEMO must never appear on the same page.** REAL and DEMO run the **identical**
  computation path and differ only in provider; the **fundamental** panel is still 暂无数据 in
  REAL mode because no real fundamental feed is wired — do NOT "improve" that by showing demo
  fundamentals beside a live price.
- **Quotes, K-line history, fundamentals and announcements are FOUR separate feeds**, each with
  its own provider and `source_label`. Never collapse them into one data-source claim.
- **News must never be generated, paraphrased or summarised.** `body_summary` is intentionally
  empty because the source carries no body text; the Terminal links to the original document.
  Do NOT "improve" the panel by writing summaries.
- **Symbol association comes from the payload's own `codes[]`**, never from the fact that we
  queried that symbol — an item that does not name the company must be excluded, not attributed.
- **DEMO mode has no news source and must say so.** Never synthesise headlines, and never let a
  REAL failure fall back to a DEMO answer.
- **PB (and anything like it) must be vendor-reported, never derived.** A derived PB was wrong
  for the dual-listed 000333; the vendor's own figure is the only safe one.
- **A metric no verifiable source reports stays `None`.** 营收/净利润/毛利率/净利率/EPS/ROE render
  as 暂无数据 with a reason — do NOT compute them from other fields to fill the panel.
- **A blank vendor metric becomes `None`, never 0.0**, which would read as a real measurement.
- **The market-cap identity guard must stay.** It is what pinned field [73] as total share
  capital; removing it would let a silent vendor reordering show a wrong market cap.
- **Indicator availability is decided PER INDICATOR**, by each function's own warm-up. Do not
  reintroduce a blanket threshold: a single MACD-sized gate hides five computable readings.
- **`VENDOR_FORWARD_ADJUSTED` is not PIT.** The history series is re-adjusted as of today, so it
  is correct for displaying current indicators and **wrong for backtesting**. It must never reach
  `BacktestEngine`, Replay or any certified research path.
- **The history row layout is positional and undocumented.** Its high==max / low==min invariants
  are re-checked on every row on purpose — do not remove that check to "simplify" the parser.
- **There is no automatic REAL→DEMO fallback, and there must never be one.** A failed live fetch
  shows 暂无数据 + reason; a failed live search returns nothing.
- **The live quote source is public but UNDOCUMENTED and UNLICENSED** — no SLA, delayed quotes,
  layout could change without notice (hence the arity check). Fine for research/personal use;
  a licensed vendor is required before commercial distribution. Do not present it as licensed.
- **A halted name must never show yesterday's close as a live price.**
- **A demo quote must never be able to look live**: `GoldenQuoteProvider` hard-codes
  `GOLDEN_DATASET` and stamps the demo bar's own historical timestamp, never `datetime.now()`.
  Do not add a `data_origin` parameter to it.
- **Missing data is `暂无数据` with a reason, and the row stays in the table.** Never estimate,
  never zero-fill, never silently drop a row.
- **The plain-language technical layer is deterministic code.** `terminal_application` must not
  import from `src/llm/`, and no reading may contain 买入/卖出/目标价.
- **UI boundary is an allow-list, not a single module**: `streamlit_app.py` may import
  `research_application`, `research_analyst_application` and `terminal_application`, and nothing
  else from this project.
  `test_phase_8r_security_boundary.py`'s `FORBIDDEN_UI_IMPORTS` check is unchanged — the
  allow-list narrowing was a §9-mandated addition, never a relaxation.
- **Two real providers exist and are selected through `LLM_PROVIDER_REGISTRY`.** Gemini is the
  default; OpenAI is retained. Only registry members have an implementation — a key for a vendor
  outside it (e.g. `anthropic`) must never be treated as a capability.
- **One vendor's missing credential must never silently fall through to the other**, and a
  provider failure must never be retried against a different vendor behind the same label.
- **Vendor differences are handled, not assumed away.** Gemini returns HTTP **400** for a bad
  key (mapped to `AUTHENTICATION_FAILURE` via the body's `error.status`), puts the model in the
  URL path, uses an uppercase schema dialect that rejects `additionalProperties`, and may omit
  `candidatesTokenCount` (derived by subtraction, never zero-filled). Do not "simplify" these
  into the OpenAI shape.
- **API keys travel in headers, never in a URL.** Gemini accepts `?key=`; it is deliberately
  unused because a secret in a URL leaks into proxy logs and history.
- **A provider failure is NEVER downgraded to a synthetic narrative.** Doing so would put
  unlabelled placeholder prose where a reader expects real analysis. Generation fails closed
  instead.
- **`data_origin="REAL_PROVIDER"` is set only by the real providers**; the fakes hard-code
  `SYNTHETIC_DATA`. Never let a fake emit `REAL_PROVIDER`.
- **The API key is environment-only and must stay unloggable**: no constructor argument, no
  instance attribute, no exception message, no logging. Provider error bodies are echoed only as
  a short bounded excerpt — they are untrusted content.
- **Synthetic narrative must stay unmistakable**: opt-in only, off by default, no numerals in
  the placeholder prose, `data_origin="SYNTHETIC_DATA"` on the persisted identity, and a warning
  surfaced in the UI. **This design is awaiting explicit CEO confirmation.**
- **No single verdict is structurally impossible, not merely discouraged**: `ResearchReport`
  has no verdict/rating/recommendation/signal/target-price field, Bull and Bear are both
  mandatory, and an identical Bull/Bear pair fails closed. Do not add such a field.
- **Data Confidence is computed, never AI-rated**: `data_confidence.py` imports nothing from
  `src/llm/`, and its every sub-score is exposed so the number is auditable. Keep it that way.
- **Missing data is marked, never estimated**: an absent evidence category renders an explicit
  `NOT AVAILABLE` marker; the AI's prose for it is retained on `suppressed_ai_body` rather than
  discarded. Do not backfill, approximate, or silently omit.
- **A report store separate from `ResearchRunStore`**: a report has a different reproducibility
  contract, and extending the certified-run store would have required touching
  `result_hash`-bearing code that the Step 5 directive forbade modifying.
- **Evidence Boundary is structural, not prompted**: `LLMRequest`'s only content field is
  `evidence_payload`. No database, News-API, Market-API handle or search capability can reach a
  provider implementation. Preserve this property in any future work.
- **Absolute Scope Boundary**: Research, Factor Engineering, Backtesting, Evidence/AI synthesis,
  and Workbench UI ONLY. Zero broker or trading-execution code.
- **DataTrustGate & Zero Secrets**: strict quality gate with no `fillna(0)` fallbacks;
  `SecurityAuditManager` secret scanning; credential preflight never logs a key value.

## Constraints
- **NO Unrelated Refactoring / Unauthorized Architecture Mutations.** Do not expand into any
  "Not Completed" item above without a new explicit CEO directive.
- **NO modification of `BacktestEngine`, `CertifiedReplayEngine`, PIT gating, or
  `CorporateActionAdjuster`** unless a directive names them explicitly.
- **NO Unsanctioned Memory Tools**: do not install Mem0, claude-mem, MCP servers, or agent
  frameworks.
- **NO Credential Exposure**: never log or commit API keys or tokens.
- **NO fake PASS**: no `skip` / `xfail` / weakened assertions / swallowed exceptions to make tests
  green.
- **Local commit is expected once verification is done; NEVER push to remote without explicit
  Product Owner approval.**

## Risks
- **`.claude/DECISIONS.md` is now partially stale** (roughly lines 178–186): it still records the
  corporate-action `received_at` PIT gap and the unified-formula reconciliation as *open* items.
  Both were closed by `e100cda` and `ca5a977`. Editing `DECISIONS.md` was outside the scope of the
  sync directive that produced this file — flagged for a future documentation directive. An agent
  reading only `DECISIONS.md` could re-implement work that is already done.
- **`docs/ROADMAP.md` is stale** and its "Phase 10/11/12" labels (Paper Trading / Broker / Live
  Trading) conflict with `CLAUDE.md`'s absolute scope boundary. Do not treat it as authoritative.
- Context bloat if an incoming agent bypasses `CLAUDE.md` protocols and scans the repo broadly.
- Temptation to wire a real LLM SDK as a drive-by while touching `src/llm/` — it is deliberately
  absent and requires its own directive.

## Exact Next Action
**Await CEO Review of T5.** No further Terminal work is authorized. Every data panel is now on
real data; only the AI narrative is not. Outstanding, each needing a CEO decision rather than
code:
- **Licensed data feeds** — whether to procure them before any commercial use; all FOUR sources
  (quote, history, fundamentals, announcements) are public, undocumented and unlicensed, no SLA.
- **A source for 营收 / 净利润 / 毛利率 / 净利率 / EPS / ROE** — no verifiable free endpoint
  provides them, so those rows still read 暂无数据.
- **The real AI narrative** — needs an LLM credential (`GEMINI_API_KEY` unset; the OpenAI account
  has no quota). Not started, and not to be started without a directive.
- **T6** LLM credential/quota (`GEMINI_API_KEY` unset; OpenAI account has no quota).
Also outstanding: cloud deployment needs the CEO's Streamlit account authorization
(main file `src/app/streamlit_app.py`, **Python 3.11/3.12, not 3.13**), and `CLAUDE.md`'s
Absolute Scope Boundary still says "Research/Backtest ONLY" — the CEO deferred amending it.
On a new session or post-compaction recovery, execute the New Session Recovery Protocol
(`CLAUDE.md` §7) starting with `CLAUDE.md`.

## Do Not
- Do NOT implement live trading, broker connections, or order routing.
- Do NOT create a "Phase 10" or assign a phase number to the AI Research Analyst track.
- Do NOT wire a real LLM vendor SDK without an explicit directive.
- Do NOT expand into the five "Not Completed" items without a new directive.
- Do NOT let the analyst UI import anything but the two Application Layer modules.
- Do NOT present synthetic narrative as analysis, or make it the default when a real provider
  is available.
- Do NOT let Terminal show a fabricated price, headline or fundamental. `暂无数据` is always the
  correct answer when data is absent.
- Do NOT delete the Golden Dataset — it is the approved DEMO DATA source.
- Do NOT select or purchase a data vendor without an explicit CEO directive.
- Do NOT let REAL and DEMO data appear on one page, and do NOT add a REAL→DEMO fallback.
- Do NOT describe the current quote or history sources as licensed or SLA-backed.
- Do NOT let the forward-adjusted history series reach any backtest, replay or PIT path.
- Do NOT derive a valuation metric and present it as vendor data.
- Do NOT collapse the four feeds into a single "数据来源" claim.
- Do NOT generate, paraphrase or summarise a news item.
- Do NOT claim either real end-to-end API verification passed until it actually does.
- Do NOT broaden the live tests' narrow quota/credential skip to cover other failure categories.
- Do NOT put an API key in a URL, a log, a config file, or any persisted artifact.
- Do NOT add a `result_hash` or any prose hash to `ResearchAnalystReportIdentity`.
- Do NOT add a verdict/rating/recommendation field to `ResearchReport`.
- Do NOT let an LLM produce, adjust, or influence the Data Confidence metric.
- Do NOT push to the remote repository without explicit Product Owner approval.

## Validation Required
- `git status` — working tree clean.
- `PYTHONPATH=. ./venv/bin/pytest` — **974 passed, 13 skipped, 0 failed**.
- `git diff --check` — clean.
