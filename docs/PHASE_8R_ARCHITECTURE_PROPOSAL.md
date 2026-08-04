# Phase 8R Architecture Proposal
**Research Workbench & Low-Frequency Quant Research Interface — Design Only, No Implementation**

**Directive ID**: CEO-2026-08-03-8R
**Status**: PROPOSAL — awaiting CEO review. No production code, tests, dependencies, or data were modified to produce this document.
**Baseline**: Phase 8A frozen at commits `a3e4281` / `911ba8c`, `269 passed / 11 skipped / 0 failed`, `TUSHARE_TOKEN` unavailable. Re-confirmed by running the full suite before writing this proposal.

---

## 1. Executive Summary

The repository has zero UI, zero HTTP API, zero web framework installed, and no dependency manifest file (`requirements.txt`/`pyproject.toml` do not exist — packages were installed ad hoc into `venv/`). It does have a solid foundation to build on: `ResearchRunStore` already persists (to `data/research/runs/`) and retrieves research runs by ID; `CertifiedResearchRunExecutor`/`CertifiedReplayEngine` are the proven, adversarially-tested Phase 8A entry points; `FactorRegistry` already exposes an introspectable list of available factors. `ResearchDataAPI` (`src/quant/data/research_api.py`) — the one existing thing literally named "API" — is a PIT-gated *data query* layer for raw prices/fundamentals, unrelated to running certified research and not a candidate to route Research Run creation through.

The central architectural risk this phase must guard against — a UI that quietly becomes a second research engine — is best prevented structurally, not by convention: this proposal puts a single, thin **Research Application Layer** between the UI and Phase 8A, written as plain Python functions with no framework-specific code, so that (a) there is exactly one code path capable of reaching `CertifiedResearchRunExecutor`, and (b) that path is trivially unit-testable without running a server, browser, or UI framework at all.

Two real gaps, not previously flagged, surfaced during this audit and are called out prominently rather than glossed over: (1) `SecurityMasterRegistry` and `CorporateActionStore` have no persistence — every Phase 7/8A test builds them fresh in a fixture; a long-lived UI process needs *something* to hold this state across requests, and there is currently no seed-data story for it. (2) `data/research/` is empty in the real repository (unchanged since Phase 7I's F6 finding) — there is no dataset for a user to actually click "Run" against today. Phase 8R's MVP cannot honestly demo anything without addressing both, and this proposal's recommended scope includes a small, honestly-labeled `GOLDEN_DATASET` seed bundle for exactly that reason (§9).

---

## 2. Current Backend / Package Structure (Read-Only Findings)

- **No UI of any kind.** `find` for `*.html`, `app.py`, `server.py` matches nothing except `research_api.py` (a false positive by name only — see below) and its test.
- **No HTTP API of any kind.** No Flask/FastAPI/Django/aiohttp/etc. installed (`pip list` — full list below).
- **No dependency manifest.** No `requirements.txt`, `pyproject.toml`, or `setup.py`. `venv/` contains exactly: `duckdb`, `numpy`, `pandas`, `pyarrow`, `scipy`, `pytest`, plus their transitive dependencies. Nothing web-related.
- **Python 3.9.6** (both system and venv).
- **`ResearchDataAPI`** (`src/quant/data/research_api.py`) — despite the name, this is a PIT-gated *data access* layer (`get_prices`, `get_fundamentals`, `get_metric`) wrapping `HistoricalDataWarehouse`/`SnapshotManager`/`RevisionStore`. It predates Phase 8A, never calls `CertifiedResearchRunExecutor`, and is not the "Research API" this directive means by that term. It's a reasonable candidate for the Universe Workbench's underlying data queries, not for research-run execution.
- **`ResearchRunStore`** (`src/quant/reproducibility/store.py`) already provides `create_run`, `get_run`, `list_runs`, `get_manifest`, `get_result_manifest`, `compare_runs` — persisted to `data/research/runs/<run_id>/*.json` on disk, with an in-memory cache. This is real, working, already-tested persistence — directly reusable for "GetResearchRun"/dashboard "recent runs" without writing anything new.
- **`data/research/` and `data/manifests/` are both empty (0 files)** in the actual repository — unchanged since Phase 7I. No persisted dataset exists to research against today.
- **`docs/research/OPEN_SOURCE_QUANT_COMPARISON.md`** (pre-Phase-7 design doc) already states a project-wide preference against "Framework Lock-In... wrapping our application in heavy third-party framework bases" — cited here as existing precedent supporting a minimal-dependency recommendation (§7), not invented for this proposal.

---

## 3. Non-Negotiable Architecture Rule — How This Proposal Enforces It

The directive's core rule (UI → Application Layer → `CertifiedResearchRunExecutor` → Phase 8A, never UI → its own computation) is enforced structurally by making the Application Layer:

1. **Plain Python, framework-agnostic.** No Flask/FastAPI/Streamlit-specific code inside it — it imports only Phase 8A modules (`integrity_gate`, `certified_replay_engine`, `store`, `registry`, `security_master`, etc.) and stdlib. Whatever UI technology is chosen (§7) becomes a thin caller, not a place where logic can leak in.
2. **The only code path with permission to import `CertifiedResearchRunExecutor`.** Enforced by convention today (there is no Python "internal" keyword), but made *testable* by convention: Phase 8R's security tests (§13, item 19 of the directive) grep the UI layer's source for forbidden imports (`BacktestEngine`, `FactorRegistry`, `GenericFactorStrategy`, `PortfolioConstructor`, `CorporateActionAdjuster`) and fail the build if found — the UI layer may only import the Application Layer's public functions.
3. **Read-model functions that don't compute anything new.** `GetIntegrityReport`, `GetPortfolio`, `GetSignals` etc. are pure *projections* over what `ResearchRunStore` already persisted for a run (identity, input manifest, result manifest, artifacts) — they format and label existing certified output, never recompute factor/signal/portfolio values. The one function that *does* invoke computation is `ReplayResearchRun`, which calls `CertifiedReplayEngine.replay()` — Phase 8A's own re-verification, not a new one.

---

## 4. Mandatory Architecture Questions

**1. 当前有没有 UI？** No. Confirmed by filesystem search — zero HTML/frontend files, zero web framework installed.

**2. 当前有没有 API？** No HTTP API. `ResearchDataAPI` exists but is a PIT data-query layer, not a research-execution API, and doesn't call Phase 8A's certified path — see §2.

**3. UI 应如何调用 CertifiedResearchRunExecutor？** Never directly. UI → Research Application Layer (new, plain Python) → `CertifiedResearchRunExecutor.execute(request)`. See §3 and §6.

**4. Research Run 是否已经可以持久化？** Yes — `ResearchRunStore.create_run`/`get_run`/`list_runs` already persist to `data/research/runs/` on disk (Phase 7A, unmodified since). Directly reusable, no new persistence code needed for Research Run storage itself.

**5. 哪些数据可以直接复用？** `ResearchRunStore` (run persistence), `FactorRegistry._entries` (introspectable list of registered factors — `momentum_20d:v1`, `value_pe:v1` — for the Factor Workbench's dropdown), `PersistentDatasetManifestStore` (already supports disk persistence via `base_dir`, added in Phase 7J), `ResearchDataAPI` (for Universe Workbench's underlying PIT queries).

**6. 哪些数据必须新增 read model？** Three real gaps, none of which are new *computation* — all are new *persistence or presentation* for existing concepts:
   - **Universe naming/listing.** `SecurityMasterRegistry.get_historical_universe(as_of_date)` already computes a PIT-correct symbol list, but there is no persisted, named "Universe" entity with an ID for a UI to list and select — only an in-memory registry a caller must already have populated. Needs a thin `UniverseDefinition` read model (`universe_id`, human label, underlying `SecurityMasterRegistry` snapshot reference) — presentation wrapper, not a new PIT engine.
   - **Integrity status projection.** Nothing today turns a stored `ResearchRunIdentity`/`ResearchInputManifest` into the VERIFIED/NOT VERIFIED/SKIPPED/REPRODUCIBLE/MISMATCH badge set the directive's dashboard (§4, §9) requires — needs a pure formatting function over already-certified fields, not new verification logic.
   - **Report rendering.** No report generator exists anywhere in the codebase (confirmed by search) — needs new code, but it is a *renderer* consuming `ResearchRunStore.get_run()`'s output, never a second calculator.

**7. 如何避免 UI 创建第二套计算逻辑？** §3's structural answer, plus: the Application Layer's functions are named and scoped 1:1 with the directive's requested API surface (§13) precisely so there is never a "convenient" reason for a UI developer to reach past it for a value that's "almost" available. Security tests (§13 below) make a violation a test failure, not just a code-review concern.

**8. Replay 如何暴露给 UI？** `ReplayResearchRun(run_id)` calls `CertifiedReplayEngine.replay()` (unmodified) and returns its `CertifiedReplayReport` (status: `REPRODUCIBLE` / `FINAL_RESULT_MISMATCH`, or a caught `IntermediateArtifactMismatchError` reformatted as a third UI-facing state, e.g. `INTERMEDIATE_ARTIFACT_MISMATCH`) directly to the UI's Integrity Panel. No new replay logic.

**9. 如何展示 PIT status？** Derived directly from already-certified data: `input_manifest.as_of`, `input_manifest.dataset_manifest_hash`, the per-factor `FactorStatus` values stored in the run's `factor_values` artifact (`VALID` / `NOT_APPLICABLE` / `INSUFFICIENT_HISTORY` / `INVALID` / `MISSING`), and `quality_notes` (which already says things like "no PIT-visible fundamental record"). All of this is already computed and stored by Phase 8A; the UI only needs to read and label it.

**10. 如何展示 provider provenance？** `artifacts["provider_data_origin"]` (stored per Phase 7J) — one of `REAL_PROVIDER` / `LOCAL_PRODUCTION_VERIFICATION_DATA` / `GOLDEN_DATASET` / `SYNTHETIC_DATA`, displayed verbatim with `REAL_PROVIDER` never asserted unless that literal tag is what's stored (which it never will be in this environment, since `TUSHARE_TOKEN` is unavailable — §15 of the directive, §9 of this proposal).

**11. 如何生成 research report？** New `GenerateResearchReport(run_id)` function in the Application Layer: reads the full stored run via `ResearchRunStore.get_run()`, plus a fresh `ReplayResearchRun()` call for the Integrity section, and renders to Markdown (simplest, human-readable, diffable, git-friendly, no new rendering dependency) with an optional HTML/PDF export as a v2 nice-to-have, not MVP.

**12. 如何保证 UI 与 backend 的结果一致？** There is only one "backend" in this design — the Application Layer functions the UI calls are the same functions the integration tests call (§13). There is no separate "UI backend" that could drift from a "real backend"; if UI and API were split into separate processes later (§7's alternative), the same Application Layer module would be imported by both, not reimplemented.

**13. 如何测试 UI 不绕过 certified execution path？** Three layers (§13 below): backend unit tests (Application Layer function → `CertifiedResearchRunExecutor`, asserting the call actually happens, not a stand-in), integration tests (full UI-request-shaped input → Application Layer → Phase 8A → stored `ResearchRun` → replay → formatted result), and a static/security test that greps the UI layer's own source for forbidden direct imports of Phase 8A internals.

**14. 如何处理 TUSHARE_TOKEN 缺失？** Every UI surface that would show live-provider status reads it honestly from stored data (`provider_data_origin`, the existing 11-test skip reasons) — never a hardcoded "connected" state. For the MVP to have *anything* to research against, given `data/research/` is empty, Phase 8R's scope includes a small, explicitly-`GOLDEN_DATASET`-tagged seed bundle (Momentum+Value fixture data, same shape as Phase 8A's own test fixtures) that a user can select and run against — labeled as what it is at every point in the UI, never presented as if it were real market data.

**15. 如何保持 research-only boundary？** No broker/order/trading imports anywhere in the new code (enforced by the same static grep test as item 13, extended to also forbid trading-related terms). The Application Layer's function surface (§13) has no "place" for an order to go — `CreateResearchRun` produces a `ResearchRunIdentity`, not a trade.

---

## 5. Target Architecture

```
┌─────────────────────────────────────────────────────────┐
│  UI (Streamlit pages OR Jinja2-rendered HTML — §7)       │
│  - Research Dashboard, Universe/Factor/Portfolio/         │
│    Backtest Workbenches, Replay/Integrity Panel,          │
│    Research Run Page, Report export button                │
└───────────────────────┬─────────────────────────────────┘
                         │  plain function calls (same process, MVP — §7)
┌───────────────────────▼─────────────────────────────────┐
│  Research Application Layer  (NEW — src/app/research_    │
│  application.py, plain Python, zero UI-framework imports) │
│                                                            │
│  CreateResearchRun(params) -> CertifiedResearchRunExecutor│
│  GetResearchRun(run_id) -> ResearchRunStore.get_run       │
│  ListResearchRuns() -> ResearchRunStore.list_runs         │
│  ReplayResearchRun(run_id) -> CertifiedReplayEngine.replay│
│  GetUniverse(as_of, universe_id) -> SecurityMasterRegistry │
│  GetFactorDefinitions() -> FactorRegistry (introspection)  │
│  GetSignals(run_id) / GetPortfolio(run_id) -> artifact     │
│    projection (read-only formatting, no computation)       │
│  GetIntegrityReport(run_id) -> field projection + replay   │
│  GenerateResearchReport(run_id) -> Markdown renderer        │
└───────────────────────┬─────────────────────────────────┘
                         │  unmodified Phase 8A/7 imports
┌───────────────────────▼─────────────────────────────────┐
│  CertifiedResearchRunExecutor / CertifiedReplayEngine /    │
│  FactorRegistry / ResearchRunStore / SecurityMasterRegistry│
│  (Phase 7 + Phase 8A — UNMODIFIED)                          │
└─────────────────────────────────────────────────────────┘
```

---

## 6. Application API — Proposed Surface

Matches the directive's §13 list; names adjusted only to match existing project naming conventions (snake_case module-level functions, matching `research_api.py`'s style) rather than PascalCase:

| Directive name | Proposed function | Wraps (unmodified) |
|---|---|---|
| `CreateResearchRun` | `create_research_run(params: ResearchRunParams) -> ResearchRunIdentity` | `CertifiedResearchRunExecutor.execute` |
| `GetResearchRun` | `get_research_run(run_id: str) -> ResearchRunView` | `ResearchRunStore.get_run` |
| `GetResearchResult` | `get_research_result(run_id: str) -> BacktestResultView` | `ResearchRunStore.get_result_manifest` + artifacts |
| `ReplayResearchRun` | `replay_research_run(run_id: str) -> ReplayView` | `CertifiedReplayEngine.replay` |
| `GetUniverse` | `get_universe(as_of: date, universe_id: str) -> UniverseView` | `SecurityMasterRegistry.get_historical_universe` |
| `GetFactorDefinitions` | `get_factor_definitions() -> List[FactorDefinitionView]` | `FactorRegistry._entries` (read-only introspection) |
| `GetSignals` | `get_signals(run_id: str) -> List[SignalView]` | run artifacts (`factor_values`, composite scores if stored) |
| `GetPortfolio` | `get_portfolio(run_id: str) -> PortfolioView` | run artifacts (`portfolio_weights`) + `result_manifest` |
| `GetIntegrityReport` | `get_integrity_report(run_id: str) -> IntegrityReportView` | identity/manifest field projection |
| `GenerateResearchReport` | `generate_research_report(run_id: str) -> str` (Markdown) | all of the above, composed |

`*View` types are new, simple, frozen dataclasses — UI-facing DTOs, not new domain models. `ResearchRunParams` (the `CreateResearchRun` input) is a UI-friendly wrapper that the Application Layer translates into a full `CertifiedResearchRequest` — this translation step is exactly where "UI selects a date/universe/factor config" becomes "certified request," and it is the one place worth a dedicated adversarial test proving it cannot construct an invalid/incomplete `CertifiedResearchRequest` that would silently bypass a Phase 8A control (e.g., proving the translation can't accidentally omit `signal_config` and thereby hit some hypothetical default — Phase 8A already has no such default, so this test is a regression guard, not a new control).

---

## 7. UI Technology Decision — Two Options, Recommendation Given

**Constraint recap**: no existing frontend, no dependency manifest, Python 3.9.6, single low-frequency user (the CEO), explicit CEO preference against a large frontend ecosystem, existing project precedent (§2) against framework lock-in.

### Option A (recommended): Streamlit, single-process, no HTTP hop
- UI *is* Python — no HTML/CSS/JS/build toolchain at all. Widgets (`st.selectbox`, `st.dataframe`, `st.line_chart`, `st.button`) map close to 1:1 onto every requested workbench (date/universe/factor pickers, run tables, equity curve, status badges).
- Runs as one process; pages import the Application Layer's functions directly — zero serialization/network layer to get wrong for v1.
- New dependency: `streamlit` only (plus its own transitive deps — notably, it is a substantial package, but it is *one* `pip install`, not an npm ecosystem).
- **Risk to flag**: Streamlit reruns the whole script on every widget interaction. Without care, this could re-trigger `create_research_run` (an expensive, side-effecting call) on an unrelated click. Mitigation: gate all side-effecting calls behind an explicit `st.button("Run")` plus `st.session_state` caching of the resulting `run_id` — a concrete implementation rule for Step 2, not a reason to reject the option.

### Option B: FastAPI (JSON API) + Jinja2 server-rendered HTML
- Conventional client-server split; the Application Layer is wrapped in real HTTP endpoints (matches the directive's API-boundary language most literally).
- Better fit if multi-device/remote access is ever wanted without a rewrite.
- New dependencies: `fastapi`, `uvicorn`, `jinja2` (or `flask` as a lighter-weight alternative to FastAPI if async/OpenAPI generation isn't valued) — more moving parts than Option A, but each individually small and mature.
- Requires writing HTML templates and a bit of vanilla JS/CSS for anything beyond the simplest forms/tables — more code for the same MVP feature set than Option A.

**Recommendation**: **Option A (Streamlit)** for the MVP, because it minimizes total new surface area (no templates, no JS, no separate client/server processes to keep in sync) while satisfying every requested workbench, and because the Application Layer is designed framework-agnostically (§3/§6) — nothing is lost if Option B is wanted later; the Application Layer would be reused as-is under FastAPI endpoints. This is a judgment call, not a fact, and is flagged as an Open Question (§26) for explicit CEO confirmation before Step 2 begins, matching how the Phase 8A proposal surfaced its own open fork rather than silently deciding.

### Dependency management
Recommend creating `requirements.txt` (simplest option, matches the project's existing lack of `pyproject.toml` complexity) pinning exact versions of whatever is approved. Not created in this Step 1 deliverable — proposal only.

---

## 8. Persistence

| Concern | Status | Plan |
|---|---|---|
| Research Run records | Already persisted (`ResearchRunStore`, disk-backed) | Reuse as-is |
| Dataset manifests | Already persisted (`PersistentDatasetManifestStore(base_dir=...)`, Phase 7J) | Reuse as-is; Application Layer constructs it with a `base_dir` under `data/manifests/` |
| Security master / universe definitions | **In-memory only, no persistence** | New: a small JSON-backed seed loader (not a new PIT engine — a bootstrap step populating `SecurityMasterRegistry` at process start from a checked-in seed file) |
| Corporate actions | **In-memory only, no persistence** | Same pattern — seed loader populating `CorporateActionStore` at process start |
| Actual market/fundamental dataset | **Empty in the real repo** (`data/research/` has 0 files) | New: a small, explicitly `GOLDEN_DATASET`-tagged demo dataset generated once and persisted via the existing `ParquetStorageAdapter` + `PersistentDatasetManifestStore`, so the MVP has something real to run against without fabricating live data |

---

## 9. Reporting

`generate_research_report(run_id)` composes (§4 Q11) into the Markdown structure the directive specifies (§11): Executive Summary, Factor Analysis, Portfolio, Backtest, Integrity, Limitations. The **Limitations** section is generated, not hand-written per report — a fixed list (live provider unavailable, `turnover`/`trade_count`/cost-model limitations from Phase 8A's own disclosed deferrals) is always appended, so it cannot be silently dropped by a future UI change.

---

## 10. Failure / Fail-Closed Model for the UI Layer

- `create_research_run` propagates `CertifiedResearchRunExecutor`'s `ValueError("FAIL CLOSED: ...")` verbatim to the UI as a visible error message — never caught-and-hidden, never silently retried with different parameters.
- `replay_research_run` surfaces `IntermediateArtifactMismatchError` and `FINAL_RESULT_MISMATCH` as distinct, differently-labeled UI states (directive §9's exact three-state requirement), not collapsed into one generic "failed."
- Missing `TUSHARE_TOKEN` never produces a UI error — it is not an error state, it is an honest `NOT VERIFIED` label (directive §15).

---

## 11. Testing Requirement — Three Layers

1. **Backend/unit tests** (`tests/test_research_application_layer.py`, proposed): call each Application Layer function directly, assert it invokes the real Phase 8A component (e.g., via a `unittest.mock.patch` spy on `CertifiedResearchRunExecutor.execute` to prove it was called with a correctly-translated request — spying, not stubbing out the real logic) and that the returned `*View` object's fields trace back to genuine `ResearchRunIdentity`/`BacktestResult` fields, not fabricated placeholders.
2. **Integration tests**: full path — construct `ResearchRunParams` shaped like real UI input → `create_research_run` → `get_research_run` → `replay_research_run` → assert `REPRODUCIBLE`. This is the directive's exact "UI request → API → CertifiedResearchRunExecutor → Backtest → ResearchRun → Replay → UI result" chain, driven without any actual UI framework running (calling the Application Layer functions is sufficient — the UI layer itself has no logic to integration-test beyond "does it call the right function," which is a thinner, separate concern).
3. **Security tests**: (a) static source grep proving the UI layer module never imports `BacktestEngine`/`FactorRegistry`/`CorporateActionAdjuster`/`PortfolioConstructor`/`GenericFactorStrategy` directly; (b) proving no credential/token string ever appears in a UI-facing view object or log line; (c) proving the Application Layer's public function set contains no order/trade/broker-shaped function (name-based assertion against the directive's forbidden-verb list: `place_order`, `execute_trade`, `connect_broker`, etc. — a regression guard, not a defense against a determined bad actor, but appropriate for this project's "prevent a governance mistake" threat model).

---

## 12. Phase 8A Preservation

Zero lines of Phase 8A code (`integrity_gate.py`, `certified_replay_engine.py`, `engine.py`, `registry.py`, `generic_factor_strategy.py`, `manifest.py`, `identity.py`) are modified by this proposal's design. Every Application Layer function is additive, calling existing public methods with existing signatures. If Step 2 implementation finds a Phase 8A interface insufficient for the UI's needs (e.g., `ResearchRunStore` lacking a pagination method for a long run history), the correct response per directive §21 is STOP and report, not a silent edit — flagged here as the expected process, not pre-emptively worked around.

---

## 13. Risks

1. **Streamlit rerun-on-interaction model** (§7) — concrete mitigation identified, not just a warning.
2. **No seed data story existed before this audit** — addressed explicitly in scope (§8), not deferred silently; without it, Phase 8R's own CEO Success Criterion (§22 of the directive — "选择一个历史日期、Universe 和 Momentum + Value 配置，点击 Run") is not achievable, since there is currently nothing to select.
3. **`SecurityMasterRegistry`/`CorporateActionStore` process-lifetime-only persistence** means a UI backend restart loses accumulated state unless seeded fresh each start — acceptable for a single-user local research tool (matches "低频" positioning) but worth stating plainly rather than discovering it in Step 2.
4. **Report rendering is new code** with no existing test coverage to build on — will need its own dedicated test suite from scratch (§11 item 1 covers the Application Layer function; the Markdown formatting itself should get golden-output tests).

---

## 14. Open Questions (Require CEO Decision Before/At Step 2)

1. **Streamlit vs. FastAPI+Jinja2** (§7) — this proposal recommends Streamlit; confirm or override.
2. **Seed dataset scope** (§8/§9 of this proposal) — confirm it's acceptable for Phase 8R to generate and commit (or generate-on-first-run, not commit) a small `GOLDEN_DATASET` demo bundle (a handful of symbols, a few weeks of synthetic-but-labeled price/fundamental data) so the MVP has something to run against. Alternative: Phase 8R ships with zero seed data and requires the CEO to supply real data manually before first use — technically simpler for the CTO but means the "click Run" success criterion cannot be demonstrated without that manual step.
3. **Universe naming**: is a lightweight `UniverseDefinition` read-model (§4 Q6) sufficient, or does the CEO want a more fully-featured universe-management workflow (create/edit/version named universes)? This proposal scopes to the minimum needed for the workbench to function.
4. **Report export formats**: Markdown-only for MVP (this proposal's recommendation) vs. also generating HTML/PDF in v1.

---

## 15. Acceptance Criteria

Adopts directive §22 (CEO Success Criterion) and §23 (Hard Stop Conditions) verbatim as the acceptance criteria for the eventual implementation phase; not restated here to avoid drift between two copies of the same list.

---

**No code, tests, dependencies, or data were modified to produce this document.**

```
$ git status --short
 (only this new file, plus the pre-existing untracked .claude/)

$ PYTHONPATH=. ./venv/bin/pytest -q
269 passed, 11 skipped in 3.61s
```
