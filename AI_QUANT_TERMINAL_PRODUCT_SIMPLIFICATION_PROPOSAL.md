# AI Quant Terminal — Product Simplification & Real-Time Data Architecture

**Status**: PROPOSAL — awaiting CEO decision. No code has been written.
**Author**: CTO (Claude) · **Requested by**: CEO
**Audit basis**: repository at `5d1e998`, read-only inspection of `src/data/providers/`,
`src/data/contracts/`, `src/app/`, `src/llm/`, `src/quant/technical/`.

> **Note on the directive**: §5 "未来 API" was truncated mid-code-block after `AI Provider`.
> §6 onward (if any) was not received. This proposal covers everything through §5 as written;
> please supply the remainder when reviewing.

---

## 0. The one finding that changes the plan

The directive treats real-time data as "swap the data source". It is not. The reason is
structural and worth stating before anything else:

**Every data path in this system is keyed by `(symbol, trade_date)` — a historical daily bar.
There is no concept of "the price right now" anywhere in the codebase.**

```python
# src/data/providers/base.py — the ONLY market-data method that exists
def fetch_market_data(self, symbol: str, trade_date: str) -> Optional[MarketDataContract]
```

`MarketDataContract` carries `open/high/low/close/volume/amount/trading_date` — a **completed
day**. It has no last-traded price, no bid/ask, no as-of timestamp finer than a date, no
intraday change%. `TemporalClassification.REALTIME` exists as a *label* in the freshness model,
but **no provider anywhere ever produces a value carrying it**.

So "实时行情" is not a configuration change. It is a **new provider capability, a new contract,
and a new freshness path** — additive to the PIT engine, not a modification of it. That is good
news for safety (the certified research core stays untouched) but it means the work is real.

---

## 1. Data reality audit — what is actually real today

| Layer | Implementation | Status **today** |
|---|---|---|
| **Market — daily bar** | `LiveTuShareAdapter.fetch_market_data` → TuShare `pro.daily()`; `LiveAkShareProviderAdapter.fetch_market_data` → akshare `stock_zh_a_hist()` | **REAL code**, but `tushare` and `akshare` are **not installed**, and `TUSHARE_TOKEN` is **not set**. Never executed. |
| **Market — real-time quote** | — | **DOES NOT EXIST.** No method, no contract field, no provider. |
| **Fundamental** | `LiveTuShareAdapter.fetch_fundamental_data` → `daily_basic` + `fina_indicator` | **REAL code**, unreachable (no token/package). AkShare's equivalent **raises "not yet implemented"**. |
| **News / 公告** | `LiveNewsAnnouncementProvider` | **DOES NOT EXIST** — the class exists solely to **refuse explicitly**. No API is wired. |
| **Corporate actions** | TuShare live adapter | Real code, unreachable. AkShare's **raises "not yet implemented"**. |
| **Technical** | `compute_moving_average` / `compute_rsi` / `compute_macd` | **REAL and tested.** Volatility / Momentum / Volume **raise `NotImplementedError`**. |
| **AI** | `GeminiLLMProvider`, `OpenAILLMProvider` (stdlib HTTP, no vendor SDK) | **REAL code.** Gemini key absent; OpenAI key present but the account has **no quota**. Neither has ever completed a real call. |
| **What a user sees in the UI right now** | `GOLDEN_DATASET` — 4 symbols, 25 fabricated trading days in Jan–Feb 2024 | **100% synthetic.** |

**Summary in one line**: the plumbing for real data is largely written and tested; **not one drop
of real data has ever flowed through it**, and the single most important consumer feature —
a live price — has no plumbing at all.

---

## 2. The conflict the CEO must resolve first

The directive states three things that cannot all be true at once today:

1. 不能依赖 Golden Dataset / Synthetic 作为用户看到的主要行情来源
2. 不能编造数据
3. (implied) 产品现在就要能用

With no data credentials provisioned, removing the Golden Dataset leaves the product showing
**nothing at all**. The honest options are:

- **(A) Provision a real data vendor now.** Product becomes real. Requires a CEO decision on
  vendor + cost + account. Recommended.
- **(B) Keep Golden Dataset temporarily, but re-label it unmistakably** as a demo dataset in the
  new consumer UI, and gate the real-time panels behind "数据源未配置". Ships the UX work now,
  swaps in real data the day credentials land. No fabrication, because nothing is presented as
  real.
- **(C) Ship nothing until (A).** Safest, slowest.

**My recommendation: (B) then (A) immediately after** — the UI rebuild and the data provisioning
are independent workstreams and should not block each other. (B) never violates 不能编造数据,
because the label always tells the truth about what the number is.

---

## 3. Vendor decision — this one needs your call and your money

A-share **real-time** quotes are a licensed product. The realistic options:

| Option | Real-time? | Cost | Risk |
|---|---|---|---|
| **TuShare Pro** | Daily bars cheap; **real-time/minute data requires a high points tier** | Paid tier | Official, stable, already coded against |
| **AkShare** (`stock_zh_a_spot_em`) | Yes — East Money spot quotes, ~3s delayed | Free | **Unofficial scraping.** Breaks without warning, no SLA, ToS grey area |
| **Official exchange / licensed vendor** (Wind, Choice, 聚宽) | Yes, authoritative | Expensive, contract | Enterprise procurement |

**News** has no free reliable source either — 公告 come from 巨潮资讯/交易所, news from vendors.

**Decision required from you**:
1. Which market-data vendor, and are you willing to pay for the real-time tier?
2. Do you accept AkShare's unofficial-scraping risk as an interim source (clearly labelled)?
3. Who provisions the account and sets the credentials? I will never hold or request a key —
   it goes in the environment / platform secrets store, per the existing security rules.

---

## 4. Proposed architecture

Additive. **The certified research core (`BacktestEngine`, Replay, PIT gates, Corporate Actions,
Factor/Signal/Portfolio) is not modified.** The consumer terminal is a *second consumer* of the
same contracts.

```
                    ┌──────────────────────────────────────────┐
                    │        Consumer Terminal (new UI)        │
                    │   search → quote → AI → tech → fund →    │
                    │        news → risk → bull/bear           │
                    └────────────────────┬─────────────────────┘
                                         │  (Application Layer only)
                    ┌────────────────────▼─────────────────────┐
                    │      terminal_application.py (new)       │
                    └──┬─────────┬──────────┬─────────┬────────┘
                       │         │          │         │
        ┌──────────────▼──┐ ┌────▼──────┐ ┌─▼───────┐ ┌▼─────────────┐
        │ QuoteProvider   │ │NewsProv.  │ │FundProv.│ │TechnicalCalc │
        │ **NEW ABC**     │ │(exists,   │ │(exists) │ │(exists,      │
        │ get_quote(sym)  │ │ unwired)  │ │         │ │ 3 indicators)│
        └─────────────────┘ └───────────┘ └─────────┘ └──────────────┘
                       │         │          │         │
                    ┌──▼─────────▼──────────▼─────────▼────────┐
                    │   DataTrustGate (existing, unchanged)    │
                    │   → Evidence Layer (existing, unchanged) │
                    └────────────────────┬─────────────────────┘
                                         │
                    ┌────────────────────▼─────────────────────┐
                    │  AI Provider (Gemini/OpenAI, existing)   │
                    │  → StructuredResearchOutput → Validator  │
                    └──────────────────────────────────────────┘
```

### 4.1 New: `QuoteProvider` ABC + `QuoteContract`

The one genuinely new abstraction. Mirrors the established provider pattern exactly.

```python
@dataclass(frozen=True)
class QuoteContract:
    symbol: str
    display_name: str
    last_price: float
    prev_close: float
    change: float                 # computed, not vendor-reported
    change_pct: float
    open_price: float
    high_price: float
    low_price: float
    volume: float
    amount: float
    quoted_at: datetime           # vendor's own timestamp
    received_at: datetime         # when WE received it
    market_session: str           # reuses existing MarketSessionEngine
    trading_status: str
    freshness: str                # REALTIME | DELAYED_REALTIME | STALE — existing enum
    data_origin: str              # REAL_PROVIDER | GOLDEN_DATASET — existing vocabulary
    provider_id: str
```

`quoted_at` + `received_at` + `freshness` exist so the UI can always answer **"这个价格是几点的"**
— the directive's own "数据更新时间 / 数据来源" requirement, enforced by the type rather than by
UI convention.

### 4.2 Everything else reuses what exists

- **News**: implement `LiveNewsAnnouncementProvider` against a chosen vendor. The ABC, contract,
  validation, dedup and PIT filter are all already built and tested.
- **Fundamental**: wire the existing `LiveTuShareAdapter.fetch_fundamental_data`.
- **Technical**: MA/RSI/MACD already exist. Volume/Momentum/Volatility need implementing
  (3 functions, currently `NotImplementedError`).
- **AI**: unchanged. The Evidence Bundle → LLM → validator → report chain works today.

---

## 5. UI restructure — hiding complexity without deleting it

**Principle: the machinery stays, the vocabulary goes.** Nothing in the certification core is
removed; it stops being the *front page*.

Proposed: **two modes, one codebase.**

| | **Terminal mode** (default, new) | **Research mode** (existing, unchanged) |
|---|---|---|
| Audience | 普通投资者 | quant / auditor |
| Entry | 搜索股票 | configure research run |
| Vocabulary | 价格、趋势、盈利、风险 | PIT, Evidence, hash, replay |
| Pages | 行情 / AI 总结 / 技术面 / 基本面 / 新闻 / 风险 / 多空 | Workbench, Run History, AI Research Analyst |

Terminal-mode page layout, mapped to §3 of your directive:

1. **搜索 + 行情卡** — 名称、现价、涨跌幅、成交量、成交额、**更新时间**、**数据来源徽章**
2. **AI 总结** — 3–5 句白话。Every number in it still passes the existing citation validator.
3. **技术面** — MA / RSI / MACD / 量能 / 趋势, each rendered as *plain-language verdict + the
   number*, e.g. `MACD 偏强 — 近期上涨动能仍在 (DIF 1.24 > DEA 0.98)`
4. **基本面** — 营收/净利/EPS/ROE/毛利率/现金流/PE/PB, missing values render **`暂无数据`**
5. **新闻公告** — 标题/时间/来源/摘要, with a hard visual separation between
   **事实（新闻原文）** and **AI 解读**
6. **风险** — 主要风险 / 次要风险 / 风险来源
7. **看多 / 看空** — two columns, both mandatory, **no 买入/卖出 verdict**

### 5.1 What must NOT be simplified away

Simplifying the *presentation* must not weaken the *guarantees*. These stay, silently:

- Citation validation — every number the AI writes still traces to real evidence, or the report
  fails closed.
- `暂无数据` markers — driven by the existing missing-category machinery, never by an AI choice.
- No verdict — `ResearchReport` still has no verdict/rating field.
- Data provenance — every panel still knows whether it is showing `REAL_PROVIDER` or demo data.

**A professional flag**: as the audience shifts from quants to retail investors, the
no-verdict and disclaimer discipline becomes *more* important, not less. A retail user is far
more likely to read "趋势偏强" as advice. I recommend the "不构成投资建议" banner be persistent
in Terminal mode, not tucked in an expander.

---

## 6. Proposed phasing

Each phase is independently shippable and independently authorizable.

| Phase | Deliverable | Blocked on |
|---|---|---|
| **T1** | `QuoteProvider` ABC + `QuoteContract` + validation + a Golden-backed adapter, all clearly labelled demo | nothing |
| **T2** | Terminal-mode UI (all 7 panels) reading from the Application Layer | T1 |
| **T3** | Real market-data adapter (vendor per §3) — the moment credentials exist, T1's labels flip to `REAL_PROVIDER` | **CEO: vendor + account** |
| **T4** | Real news provider | **CEO: vendor** |
| **T5** | Remaining technical indicators (Volume/Momentum/Volatility) | nothing |
| **T6** | Real AI narrative | **CEO: LLM quota/key** |

T1, T2 and T5 can start immediately and require nothing from you. T3/T4/T6 are credential-gated.

---

## 7. Governance note

`CLAUDE.md` currently states an Absolute Scope Boundary of *"Research, Backtesting, Factor
Analytics, and PIT Data Integrity ONLY"*. This directive repositions the product toward a
consumer analysis terminal. That is still analysis, not trading — the prohibitions on broker
integration, order execution and buy/sell verdicts are untouched and I recommend they stay
absolute. But the boundary statement itself should be **explicitly amended by you**, rather than
quietly stretched by me.

---

## 8. Decisions required before implementation

1. **Approve or amend §2's option (B)** — build the Terminal UI now against clearly-labelled demo
   data, swap in real data when credentials land.
2. **Choose a market-data vendor** and confirm who provisions/pays (§3).
3. **Choose a news source** (§3).
4. **Confirm the two-mode structure** (§5) — Terminal default, Research retained.
5. **Amend `CLAUDE.md`'s scope boundary** to cover the consumer terminal (§7).
6. **Supply the truncated remainder of the directive** (§5 onward).

No code will be written until these are answered.
