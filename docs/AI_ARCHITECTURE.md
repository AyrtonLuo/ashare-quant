# 🤖 AI Architecture — Copilot & Natural Language Integration

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-001`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. AI Layer Role & Strict Boundaries

The **AI Research Layer** serves as an intelligent natural language copilot and explanation engine.

### Strict Boundaries:
- **AI CAN**: Parse user prompts, translate natural language into structured tool calls, explain mathematical factor outputs, summarize financial filings, and format risk reports.
- **AI CANNOT**: Invent or guess stock prices, PE, PB, returns, Sharpe ratios, volatility, or factor values.
- **AI MUST**: Invoke deterministic Quant Engine endpoints via verified Data Contracts to retrieve all numeric data.

---

## 2. Agent Tool Invocation Flow

```text
User Natural Language Query
("帮我分析 600519.SH 近期的估值与动量因子")
                 │
                 ▼
┌──────────────────────────────────┐
│ Intent Parser & Tool Selector   │ -> Identifies stock code "600519.SH"
└────────────────┬─────────────────┘
                 │
                 ▼
┌──────────────────────────────────┐
│ Quant Tool Invocation            │ -> Calls QuantEngine.get_stock_factors("600519.SH")
└────────────────┬─────────────────┘
                 │
                 ▼
┌──────────────────────────────────┐
│ Validated Quant Result Returned │ -> {pe_ttm: 28.4, return_20d: 0.045, quality: "VERIFIED"}
└────────────────┬─────────────────┘
                 │
                 ▼
┌──────────────────────────────────┐
│ Explanation & Copilot Response   │ -> Formats mathematical evidence into plain language
└──────────────────────────────────┘
```

---

## 3. Registered Tool Interfaces

1. `get_stock_quote(symbol)`: Returns verified market data and price status.
2. `get_stock_fundamentals(symbol)`: Returns point-in-time financial metrics with data lineage.
3. `get_factor_scores(symbol)`: Returns Z-score normalized and neutralized factor scores.
4. `run_backtest(strategy_spec)`: Triggers Backtest Engine and returns deterministic returns/drawdown metrics.
5. `check_portfolio_risk(portfolio_spec)`: Triggers Risk Engine check.
