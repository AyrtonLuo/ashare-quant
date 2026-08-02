# 📊 Performance Analytics Specification — Metrics & Equal Weight Benchmark

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-006A`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Analytics Mathematical Formulas

1. **Sharpe Ratio**:
   $$\text{Sharpe} = \frac{\text{Annualized Return} - R_f}{\text{Annualized Volatility}}$$
2. **Maximum Drawdown**:
   $$\text{Max Drawdown} = \max_{t} \left( \frac{\max_{\tau \le t} Peak_\tau - Equity_t}{\max_{\tau \le t} Peak_\tau} \right)$$
3. **Equal Weight Benchmark**: `EqualWeightBenchmark` computes baseline portfolio performance across the stock universe.
