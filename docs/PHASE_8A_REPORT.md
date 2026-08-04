# 🏛️ Phase 8A Executive Report
**Factor Engine & Research Signal Certification**
**Directive IDs**: CEO-2026-08-03-RESEARCH-008A, -STEP2, -IMPLEMENT, -HARDEN-BACKTEST, -HARDEN-BACKTEST-REVIEW
**Target Repository**: `/Users/yuhanluo/ashare-quant`
**Git Branch**: `main`
**Base Commit**: `cd6d312` (Phase 8A architecture proposal). **This work**: uncommitted at time of writing, per CEO directive §13 ("不要立即commit... CEO review后再决定commit") — update this line once committed.

---

## 1. Executive Summary

Phase 8A had two parts. **Part 1 (prerequisite hardening, already CEO-reviewed and approved)**: a read-only inspection ahead of factor orchestration found that `BacktestEngine.run_backtest` accepted `portfolio_targets` but never read `.weights` in its return calculation — a 100%-long-winner and 100%-long-loser portfolio produced byte-identical results. This predated Phase 8A (present since Phase 7A) and blocked the entire causal chain the directive requires. Fixed, with a discovered-and-fixed companion bug in `replay_engine.py` (its equal-weight reconstruction referenced the declared universe rather than the symbols actually present in the replayed price artifact). Both fixes were CEO-reviewed and approved before Step 3 resumed.

**Part 2 (factor orchestration)**: the read-only audit before implementation found that almost every component a Factor Engine needs already existed — `BaseFactor`, four concrete factors, `FactorNormalizer`, `MultiFactorEngine`, `SignalEngine`, `SimpleMomentumStrategy`, `PortfolioConstructor` — each independently unit-tested, none ever called from the certified path. This phase adds `FactorRegistry` (making `factor_id` strings resolve to exactly one executable implementation), mandatory `factor_definitions`/`fundamental_data`/`signal_config` on `CertifiedResearchRequest`, wires the full factor → normalization → signal → portfolio chain into `CertifiedResearchRunExecutor` (replacing the removed hard-coded equal-weight block), and extends `CertifiedReplayEngine` to fully recompute that chain from source at replay time rather than trusting cached artifacts.

**Verdict: PASS WITH LIMITATIONS.** All CEO acceptance criteria (§15/§16/§11 across the directive sequence) are met by direct code re-reading, not test-trust alone. Limitations are the same class already disclosed and CEO-deferred: `BacktestResult.turnover`/`trade_count` remain unrelated placeholder fields, `TransactionCostModel` remains disconnected from real turnover, and live-provider verification remains unchanged (`TUSHARE_TOKEN` unavailable).

---

## 2. Files Changed

**New (5):**
`src/quant/factors/registry.py` (`FactorRegistry`), `src/quant/strategies/generic_factor_strategy.py` (`GenericFactorStrategy`, independent implementation per CEO ruling), `tests/test_backtest_engine_weight_hardening.py` (14 tests), `tests/test_factor_engine_adversarial.py` (27 tests), this report.

**Modified (8):**
`src/quant/backtest/engine.py` (weight-consumption hardening), `src/quant/reproducibility/replay_engine.py` (universe-reconstruction bug fix), `src/quant/reproducibility/identity.py` / `manifest.py` (new `signal_configuration_hash`/`signal_config` trailing-defaulted fields), `src/data/validation/pit_gate.py` (`filter_pit_fundamentals`), `src/quant/research/integrity_gate.py` (full factor orchestration, equal-weight removed), `src/quant/reproducibility/certified_replay_engine.py` (full factor/signal/portfolio recomputation, `IntermediateArtifactMismatchError`/`FINAL_RESULT_MISMATCH` distinction), `tests/test_integrity_gate_bypass_adversarial.py` (fixture updated for mandatory `factor_definitions` — no assertion weakened, no test deleted).

No file under Phase 7A–7J's PIT/snapshot/revision/immutability/corporate-action/canonical/secret-audit core was modified beyond what's listed above.

---

## 3. Architecture Changes

See §4 of `PHASE_8A_ARCHITECTURE_PROPOSAL.md` for the target design; implementation matches it, with two changes made explicit here:

1. **`BacktestEngine` hardening was a prerequisite**, not anticipated in the original proposal — discovered during implementation (see §11 for the full story) and CEO-approved as in-scope before factor orchestration resumed.
2. **`CertifiedReplayEngine` no longer delegates its final step to `ResearchReplayEngine`** for certified runs. The proposal anticipated recomputing factors/signals/portfolio and comparing against cached artifacts, then handing off to the base replay engine for the final hash check — but the base engine reconstructs a generic equal-weight `PortfolioTarget` from whichever symbols are in the price artifact, which is not the real certified weights. `CertifiedReplayEngine` now performs its own self-contained final backtest re-execution using the recomputed real weights, only reusing `DatasetVersionLock`/`PersistentDatasetLock`/`CorporateActionAdjuster` directly rather than going through `ResearchReplayEngine`.

---

## 4. Mandatory Enforcement Evidence — Factor Execution Chain

Verified in `src/quant/research/integrity_gate.py` (Controls 7–12) by direct code citation:

| Step | Code | Consumes real upstream output? |
|---|---|---|
| Factor resolution | `FactorRegistry.resolve_all(sorted_specs)` (line 174) | Resolves the exact caller-supplied `factor_definitions` |
| signal_config validated against resolved factors | lines 178–195 | Rejects factor-name mismatch AND direction mismatch (no hidden override) |
| Factor calculation | lines 204–235, iterates `resolved_factors` | Market factors use `adjusted_prices` (Control 6's real output); fundamental factors use PIT-filtered `request.fundamental_data` |
| Cross-sectional normalization | line 245, `FactorNormalizer.normalize_cross_section(values)` | Operates on the just-computed `values` list, over `universe_symbols_sorted` (Control 4's locked list) |
| Composite signal | lines 251–254 | `MultiFactorEngine(sorted_signal_config).compute_composite_scores(factor_matrices)` — `factor_matrices` is the just-computed normalization output |
| Portfolio construction | lines 260–264 | `GenericFactorStrategy().generate_target_portfolio(signals, top_n)` → `PortfolioConstructor.build_portfolio(raw_weights, ...)` — `signals` is the just-computed `SignalEngine` output |
| Backtest | lines 290–295 | `daily_prices=adjusted_prices, portfolio_targets=[portfolio_target]` — the just-computed, factor-derived target, not equal-weight |

**No hard-coded equal-weight construction remains anywhere in `integrity_gate.py`** — confirmed by direct grep (zero matches for `1.0 / len(` in the file) and by `test_7_no_hardcoded_equal_weight_in_executor`, which proves Momentum-only and Value-only runs on the identical universe select different symbols.

---

## 5. Adversarial Bypass Test Matrix

`tests/test_factor_engine_adversarial.py` — 27 tests, all passing, mapped to directive §10's 20 scenarios (some scenarios get two tests where a positive/negative pair was needed):

| # | Scenario | Test | Result |
|---|---|---|---|
| 1 | Missing factor definitions | `test_1_missing_factor_definitions_fails` | TypeError (no default exists) |
| 2 | Empty factor definitions | `test_2_empty_factor_definitions_fails` | FAIL CLOSED |
| 3 | Unknown factor | `test_3_unknown_factor_fails` | FAIL CLOSED |
| 4 | Factor parameter mismatch | `test_4_invalid_factor_parameters_fails` | FAIL CLOSED |
| 5 | Factor hash mismatch / causal chain | `test_5_*`, `test_5b_*` | Hash differs; factor output differs |
| 6 | Hidden factor implementation | `test_6_hidden_direction_override_fails` | FAIL CLOSED (signal_config can't override registry direction) |
| 7 | Hard-coded equal-weight bypass | `test_7_no_hardcoded_equal_weight_in_executor` | Different factors → different weights |
| 8 | Missing fundamental data | `test_8_missing_fundamental_data_fails_closed` | FAIL CLOSED |
| 9 | Future fundamental data | `test_9_future_fundamental_data_excluded` | Excluded, not used |
| 10 | Current-only fundamental data | `test_10_current_only_provenance_rejected` | FAIL CLOSED |
| 11 | Insufficient cross-sectional sample | `test_11_*`, `test_11b_*` | FAIL CLOSED; threshold can't be silently lowered |
| 12–15 | Universe/snapshot/dataset/cost-model mismatch, re-confirmed under the full factor pipeline | `test_12`–`test_15` | FAIL CLOSED / measurable difference |
| 16 | Signal configuration mismatch | `test_16_*`, `test_16b_*` | FAIL CLOSED |
| 17 | Portfolio configuration mismatch | `test_17_*`, `test_17b_*` | FAIL CLOSED |
| 18 | Replay without factor recalculation | `test_18_replay_recomputes_factors_not_cached_values` | Corrupted cache artifact doesn't affect replay — proves it's not read as an input |
| 19 | Replay with modified factor | `test_19_*` (registry), `test_19b_*` (fundamental data) | FAIL CLOSED (`IntermediateArtifactMismatchError`) |
| 20 | Replay with modified portfolio | `test_20_replay_detects_tampered_portfolio_weights_artifact` | FAIL CLOSED |

Plus `tests/test_backtest_engine_weight_hardening.py` (14 tests, TEST A–F from the prerequisite hardening directive) and `tests/test_integrity_gate_bypass_adversarial.py`'s original 25 Phase 7J tests, all still passing with updated (not weakened) fixtures.

---

## 6. Full Test Results

```
PYTHONPATH=. ./venv/bin/pytest
Baseline (start of Phase 8A):        228 passed, 11 skipped, 0 failed
After BacktestEngine hardening:      242 passed, 11 skipped, 0 failed  (+14 regression tests)
After factor engine implementation:  269 passed, 11 skipped, 0 failed  (+27 adversarial tests)
```

11 skips unchanged throughout: `LIVE_PROVIDER_CREDENTIALS_UNAVAILABLE` / `REAL_DATA_CREDENTIALS_UNAVAILABLE`, `TUSHARE_TOKEN` still unset. No skip converted to a pass by weakening its condition; no failure hidden as a skip.

**During implementation, 15 tests failed transiently** (see §11) — all traced to the single `replay_engine.py` root cause, fixed as a genuine production bug, zero tests weakened or deleted to recover green.

---

## 7. Second-Round Read-Only Code Audit

Performed by re-reading `integrity_gate.py` and `certified_replay_engine.py` fresh (cited above by line number), answering the directive's explicit stop-condition questions:

| Question | Answer |
|---|---|
| factor registry 与实际执行脱节? | **NO** — `resolved_factors` from `FactorRegistry.resolve_all()` is used directly for calculation; nothing re-derives factors from a separate source. |
| factor hash 与实际 factor 不一致? | **NO** — `factor_definition_hash` computed from `factors_config_dicts`, built from the same `sorted_specs` list passed into `resolve_all()`. Proven by test 5/5b. |
| Value factor 无法证明 PIT? | **NO** — `PITGate.filter_pit_fundamentals` + `ValuationFactorAdapter`'s existing `MetricProvenance` check, both exercised. Proven by tests 9/10. |
| normalization 使用错误 universe? | **NO** — iterates `universe_symbols_sorted`, the same list Control 4 already PIT-validated; no alternate universe source exists in the function. |
| signal 没有真正消费 factor? | **NO** — `compute_composite_scores(factor_matrices)` where `factor_matrices` is the immediately-preceding normalization output. |
| portfolio 没有真正消费 signal? | **NO** — `generate_target_portfolio(signals, top_n)` where `signals` is the immediately-preceding `SignalEngine` output. |
| BacktestEngine 又绕过 weights? | **NO** — re-verified via `test_backtest_engine_weight_hardening.py` (14 tests) independent of the gate. |
| replay 没有重新计算 factor/signal/portfolio? | **NO** — `certified_replay_engine.py` steps 5–6 recompute from `FactorRegistry` + re-verified data; tests 18/19/19b/20 prove cached artifacts are never trusted as computation inputs. |

None of the seven stop conditions in directive §12 (008A-IMPLEMENT) were triggered. No fixture was used to mask a failure; no fallback was added anywhere in this phase.

---

## 8. Known Limitations (Explicitly CEO-Deferred, Not Silently Fixed)

Per CEO directive §5 (HARDEN-BACKTEST) and §14 (HARDEN-BACKTEST-REVIEW), the following are recorded as **FUTURE HARDENING / SEPARATE DIRECTIVE**, not fixed in this phase:

1. `BacktestResult.turnover` remains hard-coded to `0.15`.
2. `BacktestResult.trade_count` remains "days simulated," not real trade count.
3. `TransactionCostModel`'s cost calculation remains `equity * 0.05` flat, `is_buy=True` always — not driven by actual position change/turnover/direction.

None of these blocked or corrupted Phase 8A's factor-orchestration correctness (verified during implementation — no STOP condition was triggered by them), so per directive they were left untouched.

Additional Phase 8A-specific limitations, disclosed per this project's established practice:

4. Market-data-level PIT (`available_at <= as_of` on raw prices) remains enforced upstream by `HistoricalDataWarehouse`/`PITGate`, not re-verified inside the gate — unchanged disclosed limitation from Phase 7J.
5. No persisted `FundamentalDataWarehouse` exists; `fundamental_data` is caller-supplied per request, matching the already-approved architecture proposal's explicit scope (§10).
6. `src/quant/portfolio/construction_v2.py` (`PortfolioConstructorV2`, with position-cap and turnover-limit logic) exists as another isolated, unit-tested-only component, noted during this phase's exploration but out of scope — the approved proposal specifies `PortfolioConstructor` (v1), not v2.
7. Live-provider network verification remains `NOT VERIFIED` — `TUSHARE_TOKEN` unavailable, unchanged from 7G/7H/7I/7J.

---

## 9. Anti-Fabrication Statement

- No real network call was made in this session; no live credentials fabricated.
- All Phase 8A test fixtures use `GOLDEN_DATASET`, never claim `REAL_PROVIDER`.
- The `BacktestEngine` weight-blindness bug (§11) was reported to the CEO before any fix was attempted, per standing instruction not to self-remediate discovered architectural problems silently.
- The `replay_engine.py` universe-reconstruction bug, found as a direct consequence of the `BacktestEngine` fix, is disclosed as a bug found and fixed, with inline OLD BEHAVIOR/NEW BEHAVIOR code comments, not presented as if it were always correct.
- The z-score-scale-invariance issue in this report's own test suite (§section below) is disclosed as a test-design correction, not hidden.
- Every "NO" answer in §7 is backed by a specific code citation, not a general assurance.

**Test-design correction disclosed**: while writing `test_19b_replay_detects_changed_fundamental_data`, uniformly multiplying every symbol's PE by 5 was initially used to simulate "tampered" fundamental data — this test failed to detect a mismatch, not because of a replay bug, but because cross-sectional z-score normalization is mathematically invariant to uniform scaling of all inputs (`(kx-kμ)/(kσ) = (x-μ)/σ`). The test was corrected to swap relative rankings instead, which does change normalized output. Recorded here because it's a real property of the normalization approach worth knowing, not swept under the rug.

---

## 10. Git Commit

Uncommitted at time of writing, per CEO directive §13 (008A-IMPLEMENT): "先完成 code change → targeted tests → full pytest → read-only audit, 然后向CEO汇报... CEO review后再决定commit." Full diff:

```
 src/data/validation/pit_gate.py                          |  15 +
 src/quant/backtest/engine.py                              |  70 ++++-
 src/quant/reproducibility/certified_replay_engine.py       | 249 ++++++++++----
 src/quant/reproducibility/identity.py                      |   6 +
 src/quant/reproducibility/manifest.py                      |  11 +-
 src/quant/reproducibility/replay_engine.py                 |  11 +-
 src/quant/research/integrity_gate.py                       | 196 +++++++----
 tests/test_integrity_gate_bypass_adversarial.py            |  27 +-
 + new: src/quant/factors/registry.py
 + new: src/quant/strategies/generic_factor_strategy.py
 + new: tests/test_backtest_engine_weight_hardening.py
 + new: tests/test_factor_engine_adversarial.py
```

---

## 11. The BacktestEngine Discovery (Prerequisite Hardening — Recap for the Complete Record)

Before Step 3 could begin, wiring `PortfolioConstructor`'s real output into `BacktestEngine` required verifying the engine actually used it. It did not: `run_backtest` accepted `portfolio_targets` but computed `day_return` as an unweighted average across every symbol in `daily_prices`, never reading `.weights`. Reproduction: a 100%-long-A portfolio and its exact opposite (100%-long-B) on divergent price series produced byte-identical `total_return`. This was reported to the CEO before any fix was attempted (not self-remediated), approved for in-scope fixing, implemented as a minimal change (only the `day_return` aggregation line), and surfaced one genuine downstream bug in `replay_engine.py` (weight reconstruction referenced the wrong symbol set) which was also fixed and disclosed. Full detail, regression tests, and CEO review already recorded in the conversation preceding this report; not repeated in full here to avoid duplicating an already-approved record.

---

## 12. Final Certification Verdict

**PASS WITH LIMITATIONS**

Every directive acceptance criterion across the full 008A sequence (§16 of 008A-IMPLEMENT, §11 of HARDEN-BACKTEST-REVIEW) is met:
- [x] FactorDefinition executable (via `FactorRegistry`)
- [x] FactorCalculator genuinely computes factors
- [x] SignalEngine genuinely generates signals
- [x] PortfolioConstructor genuinely consumes signals
- [x] BacktestEngine consumes real portfolio weights (hardened)
- [x] factor_definition fully bound to actual execution
- [x] PIT protection verified (market + fundamental)
- [x] current-value leak protection verified (no `datetime.now()` as `as_of`, no `fillna(0)`)
- [x] cost model verified (drives the engine; unrelated-to-turnover limitation disclosed, not hidden)
- [x] corporate actions verified (unchanged from 7I/7J, re-confirmed under the factor path)
- [x] dataset lock verified
- [x] research identity verified (new `signal_configuration_hash` bound)
- [x] replay recomputes factor, signal, and portfolio from source
- [x] result SHA-256 fully reproducible on an untampered run
- [x] adversarial tests all pass (27 new + 14 regression + 25 updated Phase 7J)
- [x] canonical serialization unified (no new competing implementation)
- [x] no fake `REAL_PROVIDER` claims
- [x] no broker / live trading / order execution — none added

Not an unqualified PASS because §8's disclosed limitations (turnover/cost-model/trade-count placeholders, upstream-only market-data PIT, no persisted fundamental warehouse) remain real, CEO-acknowledged gaps outside this phase's approved scope.

---

🛑 **STOP CONDITION**

Phase 8A is complete, tested, and code-audited. Working tree uncommitted pending CEO review.

- No Phase 8B has started.
- No broker integration, live trading, automatic execution, or real-money functionality was added.
- No live credentials were fabricated.

**CTO STANDBY — waiting for CEO REVIEW.**
