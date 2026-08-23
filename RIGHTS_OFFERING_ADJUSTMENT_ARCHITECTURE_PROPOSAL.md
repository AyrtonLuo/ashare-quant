# 🏛️ RIGHTS_OFFERING (配股) Adjustment — Architecture Proposal
## Architecture Proposal Only — No Implementation

**Status**: PROPOSAL, REVISION 2 — awaiting CEO re-review. No production code, tests,
dependencies, or data were modified to produce this document (still true of this revision).
**Directive**: CEO decision following the post-Phase-9 read-only next-phase scan (approved item
#1 of 3; items #2/#3 explicitly not authorized; `docs/ROADMAP.md` separately marked stale/for
governance, out of scope here).
**Baseline**: `main` at `6c0de31` (Phase 9 core + Application Layer addendum, fully committed).
Re-confirmed before writing: `git status` clean; `322 passed, 11 skipped, 0 failed`.

**Revision 2 — CEO round-1 review**: "暂缓代码实现，提案需小幅修订后再批准…核心方向正确" — two
required corrections, both addressed below, nothing hidden:
1. §5 (PIT Time Semantics) rewritten — Revision 1 imprecisely grouped `available_at` and
   `received_at` under "the same meaning" for corporate actions. **Corrected**: `filter_pit_
   corporate_actions()` checks **only** `available_at`; `received_at` is captured on the contract
   but not currently enforced for any corporate-action type — a pre-existing, uniform gap, not
   introduced or hidden by this proposal (see §5 for the full, exact description).
2. §3 expanded with a new §3.3 reconciling this proposal's formula against
   `docs/CORPORATE_ACTION_SPECIFICATION.md`'s composite ex-rights formula, explaining exactly
   when the codebase's existing independent-event-then-multiply implementation matches that
   spec exactly, when it's an approximation, and how simultaneous same-ex_date events (e.g.
   dividend + bonus + rights) actually behave. §6 gains 2 new combined-event tests.

Also incorporated, per CEO's other round-1 decisions: `subscription_price >= reference_price` is
confirmed **not** an error (§3.2, now stated as decided, not as an open question); `rights_ratio
<= 0` / missing / non-positive prices remain fail-closed (§4.2, unchanged); `result_hash`/Replay/
`BacktestEngine` remain untouched (§7, unchanged); no expansion to turnover, result-component
hashes, or live trading (§9, unchanged).

---

## 1. Executive Summary

`CorporateActionAdjuster._event_factor()` (`src/quant/adjustment/corporate_action_adjuster.py:88-92`)
currently fails closed, unconditionally, on `action_type == "RIGHTS_OFFERING"` — one of exactly
four corporate-action types defined in `CorporateActionContract.action_type`
(`CASH_DIVIDEND`, `BONUS_ISSUE`, `RIGHTS_OFFERING`, `STOCK_SPLIT`). Rights offerings (配股) are
a common, real A-share corporate action; any symbol whose real history includes one currently
cannot be PIT-adjusted at all — the entire `CorporateActionAdjuster.adjust()` call raises, not
just the one event. This is a real data-integrity coverage gap in an "Institutional-Grade A-Share
Quantitative Research" platform, and it has **zero test coverage today** (no test asserts even
the current fail-closed behavior).

This proposal specifies the standard, textbook 配股除权价 (ex-rights price) formula, adapted to
this codebase's **existing** single-reference-price convention (the same substitution pattern
already implemented and tested for `CASH_DIVIDEND` — see §3), two new trailing-defaulted input
fields on `CorporateActionContract`, and explicit fail-closed rules for invalid/missing input. No
change to PIT semantics, `result_hash`/`identity` definitions, or `CertifiedReplayEngine` is
required — both the certified path (`integrity_gate.py`) and Replay already call the same
`CorporateActionAdjuster.adjust()` function, so implementing the formula in one place closes the
gap for both simultaneously (see §7).

---

## 2. Current Architecture (unchanged by this proposal, restated for reference)

```
CorporateActionAdjuster.adjust(dates, raw_prices, actions, as_of)
        │
        ├── PITGate.filter_pit_corporate_actions(actions, as_of)   ← available_at <= as_of only
        │
        ├── group visible actions by ex_date
        │
        └── for each ex_date's event group:
                idx_before = last index i where dates[i] < ex_date   (last CUM-price date)
                ref_idx    = idx_before + 1  (or idx_before if window ends there)
                reference_price = raw_prices[ref_idx]   ← actual observed raw close ON/AFTER
                                                            ex_date (the codebase's existing
                                                            single-reference-price convention;
                                                            see §3 for why this matters)
                for each event:
                    factor = _event_factor(event, reference_price)
                    adj_factors[0 .. idx_before] *= factor   ← applied to all PRE-event prices
```

`_event_factor()` is the **only** place any formula lives. `adjust()`'s reference-price derivation,
PIT filtering, grouping, and cumulative-multiplication logic are unchanged by every existing
action type and would be unchanged by this proposal too — RIGHTS_OFFERING only needs a new
branch inside `_event_factor()`, the same shape as the three that already exist.

---

## 3. Formula Derivation

### 3.1 Standard (textbook / regulatory) formula

The standard China A-share 配股除权价 (theoretical ex-rights price) formula:

```
P_ex_theoretical = (P_cum + rights_ratio × subscription_price) / (1 + rights_ratio)
```

where `P_cum` = cum-rights closing price (the last trade before the rights offering takes
effect), `rights_ratio` = new shares subscribable per share held (e.g. `0.3` for the market
convention "10配3"), `subscription_price` = price per new share paid by existing shareholders.

**Sanity checks** (both must hold for the formula to be correct, and both do):
- `rights_ratio = 0` (no offering) → `P_ex = P_cum` → factor `= 1.0` (no adjustment). ✅
- `subscription_price = P_cum` (rights priced at market, no discount) → `P_ex = (P_cum +
  ratio·P_cum)/(1+ratio) = P_cum` → factor `= 1.0`. ✅ Correct: subscribing at market price
  creates no dilution, so no adjustment should apply — matches financial intuition (only a
  below-market discount dilutes existing holders' per-share value).

### 3.2 Adapting to this codebase's existing reference-price convention

`_event_factor()` receives exactly **one** `reference_price` argument, already defined by
`adjust()` as the actual raw close **on/after** `ex_date` (i.e., `P_ex_actual`, the *observed*
post-event price) — **not** `P_cum` (the pre-event price). This is visible in the existing
`CASH_DIVIDEND` branch: `factor = (reference_price - D) / reference_price`, where
`reference_price` plays the role the standard formula would assign to `P_cum`, substituted with
the actual post-event observed price instead. This substitution is a pre-existing, already-tested
design choice in this codebase (Phase 7I), not something this proposal introduces or should
"fix" — RIGHTS_OFFERING must follow the **same** substitution for internal consistency, since
`_event_factor()`'s signature gives it no other price to work with.

Applying the identical substitution (`reference_price` standing in for `P_cum`) to §3.1's
adjustment-factor form (`P_ex_theoretical / P_cum`):

```
factor = (reference_price + rights_ratio × subscription_price)
         ─────────────────────────────────────────────────────
         reference_price × (1 + rights_ratio)
```

**Re-verified sanity checks against this exact form** (both still hold after substitution):
- `rights_ratio = 0` → `factor = reference_price / reference_price = 1.0`. ✅
- `subscription_price = reference_price` → `factor = (reference_price(1+ratio)) /
  (reference_price(1+ratio)) = 1.0`. ✅
- `subscription_price < reference_price` (the normal, expected case — rights are almost always
  offered at a discount) → `factor < 1.0`, applied to pre-event prices as a downward rescale —
  same direction and same application pattern (`adj_factors[0..idx_before] *= factor`) as
  `BONUS_ISSUE` and `CASH_DIVIDEND` already use. ✅ Consistent.

**CEO-confirmed (round-1 review)**: unlike `CASH_DIVIDEND` (where `D >= reference_price` produces
a mathematically impossible non-positive adjusted price and therefore must fail closed), this
RIGHTS_OFFERING form stays finite and strictly positive for any `reference_price > 0`,
`rights_ratio > 0`, `subscription_price > 0` — including the unusual-but-not-impossible case
`subscription_price >= reference_price` (factor `>= 1.0`, a legitimate, if rare, real-world
outcome for a weak-demand rights issue). **Decision**: `subscription_price >= reference_price` is
allowed, not fail-closed — §4.2 codifies this, §6 test #8 proves the resulting factor is finite
and `>= 1.0`, and this paragraph is the retained documentation of the reasoning, per the CEO's
explicit requirement to keep both the test and the written explanation.

### 3.3 Relationship to `docs/CORPORATE_ACTION_SPECIFICATION.md`'s composite formula

That specification (v1.0.0, `CEO-2026-08-01-REBUILD-002`) documents a single, **unified**
ex-rights price formula covering cash dividend, bonus shares, and rights offering together:

```
P_ex = (P_pre - D + P_r × R) / (1 + B + R)
```

(`P_pre` = cum-event closing price, `D` = cash dividend/share, `B` = bonus ratio, `R` = rights
ratio, `P_r` = rights/subscription price — using the spec's own symbol names; `R`/`P_r` map
directly onto this proposal's `rights_ratio`/`subscription_price`.) The spec's formula does not
include a term for `STOCK_SPLIT` at all — it covers exactly three of the four action types.

The **existing, already-shipped** `CorporateActionAdjuster` implementation does not evaluate this
unified fraction. It computes each event type's factor **independently** (`_event_factor()`,
one branch per type) against a single shared `reference_price`, then **multiplies** the
independent factors together for events sharing an `ex_date` (`adjust()`'s `by_ex_date` grouping,
unchanged by this proposal, already in place since the multi-type support was first built). This
is a real, pre-existing architectural difference from the spec document, not something this
proposal introduces — the honest comparison, checked term-by-term against the spec's
single-variable specializations:

| Type | Spec's isolated-variable case | Codebase's independent factor | Match? |
|---|---|---|---|
| `BONUS_ISSUE` (B only) | `P_ex/P_pre = 1/(1+B)` | `1/(1+B)` | **Exact** — no price reference involved on either side. |
| `STOCK_SPLIT` (S) | not in the spec's formula | `1/S` | N/A — spec doesn't model split; codebase's convention is the universally standard one. |
| `CASH_DIVIDEND` (D only) | `P_ex/P_pre = (P_pre-D)/P_pre` | `(reference_price-D)/reference_price` | **Approximate** — `reference_price` (the actual observed raw close on/after `ex_date`) stands in for the spec's `P_pre` (the theoretical cum-event price); these coincide only if the market's actual post-event print happens to equal the theoretical figure. This substitution is pre-existing (Phase 7I), already shipped, already tested — not altered by this proposal. |
| `RIGHTS_OFFERING` (R only, **this proposal**) | `P_ex/P_pre = (P_pre + R·P_r)/(P_pre(1+R))` | `(reference_price + R·P_r)/(reference_price(1+R))` | **Approximate, same class as `CASH_DIVIDEND`** — identical substitution (`reference_price` for `P_pre`), not a new or different kind of divergence from the spec. |

**Why `RIGHTS_OFFERING` can reuse the existing independent-event semantic**: because for a single
isolated event on its own `ex_date` — the common real-world case, and the only case with any
existing test coverage — the codebase's decomposed factor is either an *exact* match to the
spec (`BONUS_ISSUE`) or an approximation of the *same kind and quality* the codebase has already
shipped and tested for `CASH_DIVIDEND` since Phase 7I (`RIGHTS_OFFERING`). This proposal
introduces no new category of spec divergence; it extends an existing, already-accepted one.

**Combined-event behavior** (same `ex_date`, two or more of `CASH_DIVIDEND`/`BONUS_ISSUE`/
`STOCK_SPLIT`/`RIGHTS_OFFERING` present — mechanism unchanged, already exists since multi-type
grouping was first built, exercised generically but **never tested for a specific expected
value, for any type combination, today**): `adjust()` computes **one** shared `reference_price`
per `ex_date`, evaluates each present event's factor independently against it, and multiplies
all of them together:

```
F_combined = f_dividend(P) × f_bonus(B) × f_split(S) × f_rights(P, R, P_r)   (whichever subset is present)
```

This is well-defined, deterministic, and commutative (order of multiplication doesn't matter) —
no new glue code is needed in `adjust()` itself; the new `RIGHTS_OFFERING` branch in
`_event_factor()` simply becomes a fourth term the existing loop can multiply in. **It is not**,
however, algebraically identical to the spec's single unified fraction for the combined case —
the product-of-independent-ratios form and the spec's shared-numerator/shared-denominator form
diverge whenever two or more of `D`/`B`/`R` are simultaneously nonzero, exactly as they already
silently diverge today for any existing 2-of-3 combination among `CASH_DIVIDEND`/`BONUS_ISSUE`/
`STOCK_SPLIT`. Reconciling the implementation with the spec's unified formula for the combined
case — for all four types, not just the new one — is a separate, larger, pre-existing
architectural question this proposal does not resolve (see §9).

---

## 4. Input Contract

### 4.1 New fields on `CorporateActionContract` (`src/data/contracts/corporate_action.py`)

```python
rights_ratio: Optional[float] = None        # new shares per share held, e.g. 0.3 for "10配3"
subscription_price: Optional[float] = None  # RMB price paid per new share
```

Added as **trailing, defaulted** fields (exact precedent: `data_origin` is already the trailing
default field on this same dataclass; Phase 8A's `signal_configuration_hash`, Phase 9's
`ResearchResultManifest` scalar fields follow the identical pattern). All 14 existing
`CorporateActionContract(...)` construction call sites (grepped: `golden_dataset_seed.py`,
`tushare_provider.py`, `akshare_provider.py`, and 4 test files) use **keyword** arguments
exclusively — confirmed by direct inspection, not assumed — so appending two new defaulted
fields at the end is mechanically safe and requires **zero** changes to any of them.

**Alternative considered and rejected**: making `rights_ratio`/`subscription_price` required
(no default), matching how `cash_amount_per_share`/`bonus_ratio`/`split_ratio` are already
required-with-dummy-values at every call site regardless of action type. Rejected because it
would force a mechanical edit to all 14 existing call sites for zero behavioral benefit — the
trailing-default pattern is this codebase's own established way to avoid exactly that ripple,
and the fail-closed rule in §4.2 already prevents the "missing field silently treated as valid"
risk that requiring the fields would otherwise guard against.

### 4.2 Invalid input / missing field behavior (fail-closed, no fabrication)

New checks inside `_event_factor()`'s `RIGHTS_OFFERING` branch, mirroring the existing checks'
style exactly (`STOCK_SPLIT`'s `split_ratio <= 0` check, `CASH_DIVIDEND`'s three checks):

| Condition | Behavior |
|---|---|
| `rights_ratio is None` or `subscription_price is None` | `raise ValueError("FAIL CLOSED: ...")` — a `RIGHTS_OFFERING` action with a missing economic field is not silently treated as ratio `0.0` (which would silently no-op the adjustment and mask a real corporate action — the exact fabrication risk flagged in Phase 9's own §17 risk #3). |
| `rights_ratio <= 0` | `raise ValueError("FAIL CLOSED: ...")` — mirrors `STOCK_SPLIT`'s strict `> 0` requirement; a ratio of `0` is not a real rights offering. |
| `subscription_price <= 0` | `raise ValueError("FAIL CLOSED: ...")` — mirrors `CASH_DIVIDEND`'s non-positive-price guard. |
| `reference_price <= 0` | `raise ValueError("FAIL CLOSED: ...")` — mirrors `CASH_DIVIDEND`'s existing identical check (division by `reference_price` would otherwise be undefined/nonsensical). |
| `subscription_price >= reference_price` | **Not** an error — CEO-confirmed (§3.2). Produces a well-defined `factor >= 1.0`. |

No `try`/`except`-and-continue anywhere; every failure aborts the entire `adjust()` call for that
symbol (identical to how a bad `CASH_DIVIDEND` already aborts today) — consistent with this
project's whole-adjuster fail-closed contract, not a new failure mode.

---

## 5. PIT Time Semantics

**Corrected from Revision 1**, per CEO review: Revision 1 stated `RIGHTS_OFFERING` would use
"the same `announcement_date`/`available_at`/`received_at` fields... with the same meaning" as
the other three types — accurate for the *fields*, but it did not spell out precisely what
`filter_pit_corporate_actions()` actually checks, which risked implying more protection than
exists. Corrected, exact statement below.

**What `filter_pit_corporate_actions()` actually enforces today** (`pit_gate.py:27-33`, quoted
verbatim): `return [a for a in actions if a.available_at <= as_of_cutoff]` — **`available_at`
only**. `received_at` is a real field on `CorporateActionContract` (line 25: "When this action's
payload arrived in the system"), but this gate never reads it. Contrast with
`PITGate.filter_pit_fundamentals()` (`pit_gate.py:35-47`), which explicitly checks **both**
`available_at` **and** `received_at` (and rejects either being unset) — corporate actions do
**not** get that same dual-cutoff protection today. This is **not** something this proposal
changes, introduces, or should be described as "unified dual-cutoff protection" — Revision 1's
phrasing risked exactly that impression, corrected here per the CEO's explicit instruction not to
understate it.

**Scope of this proposal regarding PIT**: `RIGHTS_OFFERING` would be gated by the exact same
(single-cutoff, `available_at`-only) check already applied uniformly to `CASH_DIVIDEND`/
`BONUS_ISSUE`/`STOCK_SPLIT` since Phase 7A — no `RIGHTS_OFFERING`-specific PIT code is needed
because no type-specific PIT code exists for any type today. Whether `filter_pit_corporate_
actions()` itself should be hardened to also check `received_at` (matching `filter_pit_
fundamentals()`'s stronger contract) is a **pre-existing, separate architectural question**,
affecting all four action types equally, not introduced by adding a fourth type — **out of scope
for this proposal** to fix (per the CEO's explicit "不修改生产代码...在上述两点修订完成前" scope
discipline), but explicitly disclosed here rather than silently carried forward. Flagged as a
candidate for a future, separate PIT-hardening directive (see §9).

**Scoping assumption, flagged explicitly**: this proposal assumes a rights offering is disclosed
as a single event carrying both `rights_ratio` and `subscription_price` together (matching the
real-world 配股说明书 disclosure practice — ratio and price are announced in the same filing).
Multi-stage disclosure (e.g. ratio announced before price is finalized) is out of scope — no
evidence in this codebase's existing contracts or golden dataset suggests any other action type
is modeled that way either, so this is consistent with existing practice, not a new limitation
introduced here.

---

## 6. Test Matrix

New tests, matching the existing `tests/test_corporate_action_integration.py` fixtures/style
(`DATES`, `AS_OF_LATE`, `_split_action()`/`_dividend_action()`-style helper) — proposed as
additions to that file, not a new file, since it already owns this exact test surface:

| # | Test | Proves |
|---|---|---|
| 1 | `test_rights_offering_applies_dilution_adjustment` | A real `RIGHTS_OFFERING` (e.g. `rights_ratio=0.3, subscription_price` at a realistic discount to `reference_price`) produces `factor < 1.0`, applied to pre-ex-date prices, matching §3.2's formula computed independently in the test (not just "some factor" — an exact expected-value assertion, same style as the existing `test_cash_dividend_applies_ex_dividend_adjustment`). |
| 2 | `test_rights_offering_at_market_price_produces_no_adjustment` | `subscription_price == reference_price` → `factor == 1.0` (§3.1/§3.2 boundary case). |
| 3 | `test_rights_offering_zero_ratio_fails_closed` | `rights_ratio == 0.0` → `ValueError`, message matches `"FAIL CLOSED"`. |
| 4 | `test_rights_offering_negative_ratio_fails_closed` | `rights_ratio < 0.0` → `ValueError`. |
| 5 | `test_rights_offering_non_positive_subscription_price_fails_closed` | `subscription_price <= 0` → `ValueError`. |
| 6 | `test_rights_offering_missing_ratio_fails_closed` | `rights_ratio=None` (default, e.g. an old/mismatched-type action) → `ValueError`, never silently treated as `0.0`. |
| 7 | `test_rights_offering_missing_subscription_price_fails_closed` | `subscription_price=None` → `ValueError`. |
| 8 | `test_rights_offering_subscription_price_above_reference_produces_valid_factor_gte_one` | Documents §3.2's explicit non-error case: `subscription_price > reference_price` → finite `factor >= 1.0`, no exception. |
| 9 | `test_rights_offering_excluded_when_available_at_after_as_of` | Same pattern as existing `test_action_not_yet_available_is_excluded_from_snapshot`, adapted to `RIGHTS_OFFERING` — proves §5's exact, corrected claim (`available_at`-only gating applies to this type identically to the other three) behaviorally, not just by code inspection. Named precisely around `available_at` specifically, not "PIT correctness" generally, per §5's correction. |
| 10 | `test_rights_offering_backward_compatible_construction_without_new_fields` | An old-style `CorporateActionContract(...)` call (only the original required fields, e.g. for a `STOCK_SPLIT`/`CASH_DIVIDEND`/`BONUS_ISSUE` action) still constructs with `rights_ratio`/`subscription_price` defaulting to `None` — proves the trailing-default addition doesn't perturb any of the 14 existing call sites (companion to, not a replacement for, actually running the full existing suite unmodified — see §9). |
| 11 | `test_certified_run_consumes_rights_offering_adjustment` | End-to-end via `CertifiedResearchRunExecutor.execute()` (same pattern as `test_integrity_gate_bypass_adversarial.py`'s existing `STOCK_SPLIT` test at line ~201): register a `RIGHTS_OFFERING`, assert the certified run's stored `artifacts["corporate_actions_applied"]` reflects it and the adjusted (not raw) price series was actually used. |
| 12 | `test_replay_reproducible_with_rights_offering_adjustment` | `CertifiedReplayEngine.replay()` on a run containing a `RIGHTS_OFFERING` action returns `REPRODUCIBLE` — proves §7's "Replay needs zero changes" claim behaviorally. |
| 13 | `test_rights_offering_combined_with_cash_dividend_same_ex_date_multiplies_factors` | **New in Revision 2**, per CEO requirement. Two actions (`CASH_DIVIDEND` + `RIGHTS_OFFERING`) sharing one `ex_date` produce `factor == f_dividend(P) × f_rights(P, R, P_r)` computed independently in the test — proves §3.3's documented product-of-independent-factors mechanism for the *new* type's interaction with an *existing* one, exactly as it actually behaves (not asserted against the spec's unified formula, since §3.3 shows those are not the same computation). |
| 14 | `test_rights_offering_combined_with_bonus_issue_same_ex_date_multiplies_factors` | Same as #13, for `BONUS_ISSUE` + `RIGHTS_OFFERING` — the other pairing directly reachable once `RIGHTS_OFFERING` exists. |

Plus: full existing regression suite re-run, unmodified — **322 passed, 11 skipped, 0 failed**
baseline must hold, exactly as every prior phase in this session required.

**Explicitly not added** (per §3.3/§9 — a pre-existing gap, not this proposal's to close): tests
for the already-shipped `CASH_DIVIDEND` + `BONUS_ISSUE` + `STOCK_SPLIT` combinations sharing an
`ex_date` remain absent today and remain absent after this proposal — they predate `RIGHTS_
OFFERING` entirely and are called out in §9 as a separate candidate item, not silently left
unmentioned.

---

## 7. Impact on Existing `result_hash` / Identity / Replay / `BacktestEngine`

**`result_hash` / `ResearchRunIdentity`**: **zero change.** `CorporateActionAdjuster` sits
strictly upstream of hash computation — its output (`adjusted_prices`) becomes the price series
`BacktestEngine.run_backtest()` consumes, which produces the `BacktestResult` whose
`{sharpe, return, mdd}` triple is what `result_hash` actually covers (unchanged since Phase 7I,
untouched by Phase 9, untouched here). Adding a new branch inside `_event_factor()` changes *what
number* the adjuster computes for a `RIGHTS_OFFERING` event, not *how* that number flows into
identity/hashing — identical in kind to how the existing three action types already work.

**`CertifiedReplayEngine`**: **zero code change required.** `certified_replay_engine.py:169`
already calls the exact same `CorporateActionAdjuster.adjust(symbol_dates, symbol_raw,
visible_actions, as_of)` function the certified path uses (`integrity_gate.py:163`) — there is
only one adjuster implementation in this codebase (per its own module docstring: "there is
exactly one place in the codebase that performs this computation"). Implementing the
`RIGHTS_OFFERING` branch in `_event_factor()` closes the gap for both the certified path and
Replay simultaneously, with no second call site to update. Test #12 (§6) proves this behaviorally,
not just by code-path inspection.

**`BacktestEngine`**: **zero change.** It only ever consumes an already-adjusted price series
(`daily_prices`); it has no knowledge of corporate-action types at all. Confirmed by grep — no
`CorporateActionAdjuster`/`RIGHTS_OFFERING` reference anywhere in `engine.py`.

**`ResearchResultManifest`'s seven `"UNAVAILABLE"` hash placeholders**: unaffected — those were
explicitly out of scope for Phase 9 (CEO decision #2, "暂不批准") and remain untouched here too;
this proposal does not read, write, or depend on them.

---

## 8. Files Changed (proposed, for a future implementation directive — not authorized here)

**Modified (2):**
- `src/data/contracts/corporate_action.py` — 2 new trailing-defaulted `Optional[float]` fields.
- `src/quant/adjustment/corporate_action_adjuster.py` — new `RIGHTS_OFFERING` branch in
  `_event_factor()` (§3.2/§4.2); `RIGHTS_OFFERING` moves from the special-cased carve-out at
  `adjust()`'s line 118 into `SUPPORTED_ADJUSTING_ACTION_TYPES` directly (the carve-out existed
  only so `RIGHTS_OFFERING` could reach `_event_factor()` and raise its own descriptive
  not-implemented error — once implemented, the generic membership check is sufficient and the
  carve-out is dead code); module docstring's "RIGHTS_OFFERING is not implemented" line (§14-25)
  updated to document the new formula in the same style as the other three.

**Extended (1):** `tests/test_corporate_action_integration.py` — 14 new tests per §6.

**Not touched:** `src/quant/backtest/engine.py`, `src/quant/reproducibility/identity.py`,
`src/quant/reproducibility/manifest.py`, `src/quant/reproducibility/certified_replay_engine.py`,
`src/quant/research/integrity_gate.py`, `src/data/validation/pit_gate.py`, any hash/replay/
identity logic, per the directive's explicit constraint.

---

## 9. Non-Goals

Not touched, considered, or designed here: live trading, broker integration, order execution;
the two Phase-9-scan items the CEO did not authorize (result-component hash population, real
turnover/trade_count backtest realism); `docs/ROADMAP.md` governance (separately tracked per CEO
decision #4); multi-stage rights-offering disclosure (§5); any change to how `STOCK_SPLIT`/
`BONUS_ISSUE`/`CASH_DIVIDEND` already compute their factors — those three are explicitly left
byte-for-byte as they are.

**Two additional items surfaced during Revision 2's corrections, explicitly disclosed and
explicitly out of scope here** (both pre-existing, both affecting all four action types
uniformly, neither introduced by this proposal):
- **Hardening `filter_pit_corporate_actions()` to also check `received_at`**, matching `filter_
  pit_fundamentals()`'s stronger dual-cutoff contract (§5). A candidate for a future, separate
  PIT-hardening directive — not folded into this proposal's scope.
- **Reconciling the existing per-type multiplicative-decomposition implementation with `docs/
  CORPORATE_ACTION_SPECIFICATION.md`'s unified composite formula**, specifically for the
  already-shipped combined-event case (§3.3) — affects `CASH_DIVIDEND`/`BONUS_ISSUE`/
  `STOCK_SPLIT` today, independent of whether `RIGHTS_OFFERING` is ever added. A candidate for a
  separate architectural review spanning all four types, not something a fourth-type addition
  should silently absorb.

---

## 10. Rollback Strategy

Additive only (trailing-defaulted contract fields, a new `_event_factor()` branch, new tests) —
rollback is a plain revert. No existing `CorporateActionContract` on disk or in any test fixture
is invalidated by adding two `Optional` fields with `None` defaults; no run persisted before this
change becomes unreadable after it, and no run persisted after this change relies on anything a
pre-change reader wouldn't already tolerate (the two new fields never appear in any hash payload).

---

## Final Report

**RIGHTS_OFFERING (配股) ADJUSTMENT — ARCHITECTURE PROPOSAL — REVISION 2**

**Status**: PASS — design-only, revised per CEO round-1 review, ready for re-review.

**Round-1 corrections applied** (nothing hidden, both fully addressed):
1. **PIT description corrected** (§5): `filter_pit_corporate_actions()` checks `available_at`
   only — `received_at` is captured but not enforced for any corporate-action type today. This
   is pre-existing (Phase 7A), uniform across all four types, not fixed by this proposal, and
   now flagged as a separate future candidate (§9) rather than being implied as already covered.
2. **Formula reconciled against `docs/CORPORATE_ACTION_SPECIFICATION.md`** (new §3.3): the
   spec's unified composite formula (`P_ex = (P_pre - D + P_r·R)/(1+B+R)`) and the codebase's
   existing independent-event-then-multiply implementation are shown to match exactly for
   `BONUS_ISSUE`, to not model `STOCK_SPLIT` at all (a spec gap, not this proposal's), and to be
   the *same class* of `reference_price`-for-`P_pre` approximation for `CASH_DIVIDEND` (already
   shipped) and `RIGHTS_OFFERING` (proposed) alike — `RIGHTS_OFFERING` introduces no new kind of
   spec divergence. Combined-same-`ex_date` behavior (product of independent factors) is
   documented exactly, shown to diverge from the spec's unified fraction in the combined case
   (pre-existing, not new), and 2 new tests (§6 #13/#14) now cover `RIGHTS_OFFERING`'s
   interaction with each existing type.

**Formula**: `factor = (reference_price + rights_ratio × subscription_price) / (reference_price
× (1 + rights_ratio))` — the standard 配股除权价 formula, adapted through the exact
single-reference-price substitution this codebase already uses for `CASH_DIVIDEND`. Two boundary
sanity checks (`ratio=0` → `1.0`; `subscription_price=reference_price` → `1.0`) verified
algebraically in §3.2; relationship to the specification document verified term-by-term in §3.3.

**Input contract**: `rights_ratio`, `subscription_price` — two new `Optional[float] = None`
trailing-defaulted fields on `CorporateActionContract`; zero ripple to all 14 existing
(keyword-argument) construction call sites.

**Invalid/missing input**: fail-closed on `None`, `rights_ratio <= 0`, `subscription_price <= 0`,
`reference_price <= 0` — never fabricated as `0.0`. **CEO-confirmed not an error**:
`subscription_price >= reference_price` (§3.2/§4.2).

**PIT semantics**: `RIGHTS_OFFERING` inherits the exact same `available_at`-only gate already
applied uniformly to the other three types — accurately restated in §5, with the pre-existing
`received_at` gap explicitly disclosed, not implied as covered.

**Testing**: 14 new tests specified (§6) — the formula, both boundary cases, five fail-closed
paths, PIT exclusion, backward-compatible construction, end-to-end certified-run + replay
reproducibility, and (new in Revision 2) two combined-same-`ex_date` interaction tests. Full
existing suite (322/11/0) must hold unmodified.

**Impact on `result_hash`/identity/Replay/`BacktestEngine`**: none structurally — the adjuster is
strictly upstream of hashing, and `CertifiedReplayEngine` already calls the identical
`CorporateActionAdjuster.adjust()` function the certified path uses, so one implementation closes
the gap for both (§7). CEO-confirmed: none of these are touched.

**Files (proposed, not yet authorized)**: 2 modified (`corporate_action.py`,
`corporate_action_adjuster.py`), 1 extended (`tests/test_corporate_action_integration.py`, now
14 new tests).

**Two items explicitly out of scope, explicitly disclosed** (§9): hardening
`filter_pit_corporate_actions()` for `received_at`; reconciling the pre-existing three-type
combined-event implementation with the specification's unified formula. Neither is introduced or
worsened by this proposal; both are flagged as separate future candidates.

**Production Impact**:
```
Production Code Modified: NO
Tests Modified: NO
Dependencies Modified: NO
Commit Created: NO
Push Performed: NO
```

**Recommendation**: **READY FOR CEO RE-REVIEW.** No implementation until approved. This document
itself remains uncommitted, per instruction.
