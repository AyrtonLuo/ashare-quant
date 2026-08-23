# Agent Handoff

_Synchronized to HEAD `0795400` (pushed to `origin/main`). Authority order per `CLAUDE.md` §2:
Actual Repository Code & Specs > Automated Test Suite > `.claude/` files > Conversation History._

## Handoff Status
READY

## Current Track
**AI Quant Research Analyst** — no phase number assigned (standing CEO instruction).
**Phase 9 is complete. Do NOT create a "Phase 10."**

Governing document: `AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md` (revision 2, repo root),
§11 Implementation Plan. **Steps 1–5 delivered, plus the §7 Research Report Generation Layer
(not a numbered §11 step). Only step 6, the Streamlit UI, remains** — not authorized by that
document; it requires its own explicit CEO directive.

## Current Objective
None in flight. The §7 Research Report Generation Layer (`0795400`) is delivered, verified,
committed, and pushed to `origin/main`. **STOP — await the next CEO directive.**

## Completed
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
1. **Streamlit UI** — §9 / §11 step 6, the last remaining unit of this track. Requires a new
   Application Layer module; only `src/app/streamlit_app.py` may import Streamlit.
   `render_report_markdown()` gives it a framework-free rendering to build on.
2. **Volatility / Momentum / Volume indicators** — `NotImplementedError` at
   `src/quant/technical/indicators.py:212,224,237`, design in each docstring.
3. **Persistent `NewsAnnouncementStore`** — news is validated/PIT-filtered in memory only; no
   stateful immutable revision store exists for news.
4. **Real LLM API integration** — deliberately absent.
5. **Category-level `historical_eligible` (§3.4)** — never implemented anywhere. The report
   marks an absent category as `NOT AVAILABLE` without distinguishing "structurally
   current-only" from "simply absent". Disclosed in `REPORT_LIMITATIONS` on every report.
6. **Semantic conflict detection between free-text news items** (§3.3's "M&A rumour later
   denied") — not deterministically decidable, so not claimed. `CONFLICT_DETECTION_SCOPE` is
   carried onto every report so "no conflicts detected" cannot be misread as "no conflicts
   exist"; surfacing that class remains the AI's narrative contract (§6).

## Current Test Baseline
- **Passed**: 583
- **Skipped**: 11 (live-provider network tests, safely skipped when `TUSHARE_TOKEN` is absent)
- **Failures**: 0
- **Test Command**: `PYTHONPATH=. ./venv/bin/pytest`

## Git Status
- **Branch**: `main`; **Working Tree**: clean; **HEAD**: `0795400`.
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
- `src/llm/` — LLM Provider interface layer (no vendor SDK; imported only by its own tests and
  by `src/quant/research_report/`).
- `src/quant/research_report/report_identity.py`, `report_store.py` — Step 5 identity + store.
- `src/quant/research_report/report.py`, `data_confidence.py` — §7 report generation +
  computed Data Confidence / conflict detection.
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
**Await a CEO directive.** No work is currently authorized. One unit remains in this track:
**§11 step 6 — the Streamlit UI (§9)**, via a new Application Layer module, with only
`src/app/streamlit_app.py` permitted to import Streamlit.
On a new session or post-compaction recovery, execute the New Session Recovery Protocol
(`CLAUDE.md` §7) starting with `CLAUDE.md`.

## Do Not
- Do NOT implement live trading, broker connections, or order routing.
- Do NOT create a "Phase 10" or assign a phase number to the AI Research Analyst track.
- Do NOT wire a real LLM vendor SDK without an explicit directive.
- Do NOT expand into the six "Not Completed" items without a new directive.
- Do NOT add a `result_hash` or any prose hash to `ResearchAnalystReportIdentity`.
- Do NOT add a verdict/rating/recommendation field to `ResearchReport`.
- Do NOT let an LLM produce, adjust, or influence the Data Confidence metric.
- Do NOT push to the remote repository without explicit Product Owner approval.

## Validation Required
- `git status` — working tree clean.
- `PYTHONPATH=. ./venv/bin/pytest` — **583 passed, 11 skipped, 0 failed**.
- `git diff --check` — clean.
