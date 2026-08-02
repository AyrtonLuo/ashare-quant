# 🧮 Multi-Factor Engine Specification — Composite Weighting & Factor Direction

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-006B`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Multi-Factor Combination Architecture

The `MultiFactorEngine` (`src/quant/factors/multi_factor.py`) combines normalized Z-score factor signals across multiple factor families (Momentum, Volatility, Liquidity, Value):

$$\text{Composite Score}_i = \sum_{k=1}^{K} w_k \cdot \text{Dir}_k \cdot Z_{i,k}$$

- **Factor Directions (`FactorDirection`)**:
  - `POSITIVE`: Higher Z-score = Preferred (e.g. Momentum).
  - `NEGATIVE`: Lower Z-score = Preferred (e.g. Volatility, PE ratio). The engine automatically flips sign ($\text{Dir}_k = -1$).
- **Weighting Models**: Equal Weight, Fixed Weight, and Strategy Configuration-driven JSON weighting.
