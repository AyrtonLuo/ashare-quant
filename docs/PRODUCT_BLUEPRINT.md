# 🚀 Product Blueprint — AI Quantitative Investment Platform

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-001`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Product Vision & Core Mission

The **AI Quantitative Investment Platform** is a next-generation quantitative investment and research platform engineered for both retail investors and professional quant analysts.

- **Primary Goal**: Democratize institutional-grade quantitative research, risk management, and portfolio intelligence.
- **Core Value Proposition**: Allow non-technical investors to access advanced quantitative factors, risk models, and backtesting via natural language and clean UI, while providing professional quant researchers with rigorous, deterministic data models and factor engines.

---

## 2. Target User Personas & Experience Design

### Persona 1: General Investor (Retail / Non-Quant)
- **Pain Point**: Overwhelmed by jargon (Sharpe, Beta, Alpha, IC, TTM, Volatility) and misleading finance media data.
- **Platform Experience**: High-level actionable insights, plain-language explanations of risk and stock metrics, visual portfolio health scores, and AI-assisted strategy design.

### Persona 2: Quant Analyst / Advanced Trader
- **Pain Point**: Inconsistent data providers, look-ahead bias, unverified financial metrics, and opaque black-box AI tools.
- **Platform Experience**: Raw data lineage tracking, point-in-time fundamental datasets, custom factor builders, deterministic backtest engines, and strict risk engine circuit breakers.

---

## 3. Product Principles (Core Axioms)

1. **Data First**: Data correctness and provenance precede all UI and AI features. Unverified data is strictly blocked from Quant Engines.
2. **Quant First**: Financial metrics (PE, PB, Dividend Yield, Volatility, Sharpe, Drawdown, Factor Scores) are strictly computed by deterministic Quant Engines, NEVER hallucinated by LLMs.
3. **Explainability**: Every recommendation, signal, and stock score must provide transparent mathematical data support.
4. **Layered Information Density**: High-level conclusions for retail users, with 1-click drill-down to institutional data for professionals.
5. **Modular Architecture**: Clean separation between Data, Quant, AI, and Web UI layers.

---

## 4. Core Product Modules & Page Blueprints

```text
                               ┌──────────────────────────┐
                               │   AI QUANT PLATFORM UI   │
                               └────────────┬─────────────┘
                                            │
   ┌───────────────┬───────────────┬────────┴──────┬───────────────┬───────────────┐
   ▼               ▼               ▼               ▼               ▼               ▼
Markets         Stocks          Portfolio      Strategies       A-VIX         AI Research
(Regime)       (Analysis)      (Exposure)      (Backtest)     (Volatility)   (Natural Language)
```

### Module 1: Dashboard & Market Overview
- **Market Regime**: Macro indicators, A-VIX index, market breadth, sector heatmaps.
- **Personal Watchlist**: Real-time prices, data trust status tags, signal updates.
- **AI Insights**: Daily quantitative market summary backed by verified data.

### Module 2: Individual Stock Analysis (`/stocks`)
- **Multi-Dimensional Matrix**: Price, Valuation (PE, PB, PS, EV/EBITDA), Fundamentals, Growth, Quality, Momentum, Volatility, Liquidity, Dividend.
- **Data Provenance Inspector**: 1-click view of data source, price timestamp, EPS period, and corporate action adjustment method.
- **AI Stock Copilot**: Natural language explanation of stock metrics and potential risks.

### Module 3: Portfolio Management (`/portfolio`)
- **Position & Exposure Matrix**: Industry exposure, factor exposure (Style, Size, Value, Volatility), liquidity score, concentration risk.
- **Performance & Risk Analytics**: Realized return, Max Drawdown, VaR (Value at Risk), Sharpe, Sortino, Beta to A-Share indices.
- **AI Portfolio Doctor**: Explains portfolio risks and diversification suggestions based on Quant Engine outputs.

### Module 4: Personalized AI Quant Plan (`/quant-plan`)
- **User Input**: Capital size, investment horizon, risk tolerance, trading frequency, target return goals.
- **Generated Framework**: Tailored quantitative asset allocation, candidate factor mixes, risk management rules, and historical backtest plan (Not automated execution orders).

### Module 5: A-Share Volatility Index (`/a-vix`)
- **A-VIX Indicator**: A composite volatility measure tracking China A-Share market stress and implied/realized volatility surface.
