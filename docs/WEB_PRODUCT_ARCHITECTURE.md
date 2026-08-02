# 🖥️ Web Product Architecture — UI & Frontend Design

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-001`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Web UI Principles

- **Aesthetics**: Sleek dark mode (`#0e1117` background), professional financial terminal theme, high information density, clean typography.
- **No Gimmicks**: Avoid cheap dashboard clutter, excessive animations, or generic stock emojis.
- **Layered UI**: Primary summary cards for general users, expandable institutional data tables for quants.

---

## 2. Navigation Architecture

```text
+-----------------------------------------------------------------------------------+
|  📈 AI QUANT PRO   [Dashboard] [Markets] [Stocks] [Portfolio] [Strategies] [A-VIX] |
+-----------------------------------------------------------------------------------+
```

---

## 3. Screen Specifications

### 1. Dashboard (`/`)
- Market Regime status card (Bull/Bear/Ranging).
- A-VIX Market Volatility gauge.
- Top AI Signals & Watchlist performance.

### 2. Stock Analysis (`/stocks`)
- Stock Selector (e.g. `600519.SH`).
- Valuation & Fundamental Metrics with Data Trust verification badge.
- Z-Score Factor Breakdown radar chart.
- AI Copilot stock analysis dialog.

### 3. Portfolio (`/portfolio`)
- Real-time NAV curve vs CSI 300 benchmark.
- Sector & Style Factor exposure breakdown.
- Risk Engine status indicators.

### 4. A-VIX Volatility Page (`/a-vix`)
- A-Share composite volatility index curve.
- Realized Volatility vs Implied Volatility term structure.
