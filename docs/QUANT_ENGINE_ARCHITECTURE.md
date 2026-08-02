# ⚙️ Quant Engine Architecture — Deterministic Calculation Core

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-001`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Quant Engine Architecture Principles

The **Quant Engine** is the deterministic mathematical heart of the platform. It operates strictly on `Canonical Data Contracts` emitted by the Data Trust Layer.

```text
Canonical Data Contracts
          │
          ▼
┌──────────────────────────┐
│ Factor Engine            │ -> Value, Growth, Quality, Momentum, Volatility, Liquidity
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Signal Engine            │ -> Z-Score Normalization, Neutralization, Rank Mapping
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Strategy Engine          │ -> Asset Universe, Rebalance Rules, Signal Weighting
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Portfolio Engine         │ -> Target Position Matrix, Turnover Control, Sizing
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Backtest Engine          │ -> Vectorized & Event-Driven Historical Simulation
└──────────────────────────┘
```

---

## 2. Factor Engine Specification

Factors are standardized quantitative metrics. Each factor implements the `FactorInterface`:

```python
from abc import ABC, abstractmethod
import pandas as pd

class FactorInterface(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass

    @property
    @abstractmethod
    def category(self) -> str: pass # Value, Growth, Quality, Momentum, Volatility

    @abstractmethod
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Computes factor values given valid Canonical Data."""
        pass
```

### Standard Factor Categories:
1. **Value**: PE_TTM_Inv, PB_Inv, Dividend_Yield.
2. **Growth**: Revenue_Growth_YoY, Net_Income_Growth_YoY.
3. **Quality**: ROE, ROIC, Gross_Margin, Debt_to_Asset_Inv.
4. **Momentum**: Return_20D, Return_60D, MA_Cross_Ratio.
5. **Volatility**: Volatility_20D, Max_Drawdown_60D.
6. **Liquidity**: Turnover_Rate_20D, Amount_Mean_20D.

---

## 3. Signal Engine & Neutralization

- **Outlier Capping**: Winsorization at 1st and 99th percentiles (MAD method).
- **Standardization**: Z-Score normalization ($\mu=0, \sigma=1$).
- **Neutralization**: Cross-sectional regression against Industry (申万一级行业) and Log Market Cap.
$$\text{Factor}_{\text{Raw}} = \beta_0 + \beta_1 \cdot \ln(\text{MarketCap}) + \sum \gamma_i \cdot \text{Industry}_i + \epsilon$$
$$\text{Factor}_{\text{Neutral}} = \epsilon$$

---

## 4. Backtest Engine Architecture

### Simulation Rules:
1. **No Look-Ahead Bias**: Point-in-time financial statements published on date $T$ become available only at market open $T+1$.
2. **Slippage & Transaction Costs**:
   - A-Share Stamp Duty: `0.05%` (Sell side only)
   - Brokerage Commission: `0.025%` (Buy & Sell, min 5 RMB)
   - Transfer Fee: `0.001%` (Shanghai & Shenzhen)
   - Slippage Model: Fixed percentage or Volume-Share impact model.
3. **Price Limits & Suspensions**: Orders for stocks hitting +10%/-10% (+20% ChiNext/STAR) price limits or suspended stocks cannot be executed.
