# 🎯 Signal Engine Specification — Recommendation Mapping & Bias Categories

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-006A`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Signal Mapping Logic

Normalized Z-Score factor values are transformed into bounded `SignalRecommendation` objects:
- **Signal Score**: Bound in range $[-1.0, 1.0]$.
- **Bias Categories**:
  - `BUY_BIAS`: Score $> 0.3$
  - `NEUTRAL`: $-0.3 \le \text{Score} \le 0.3$
  - `SELL_BIAS`: Score $< -0.3$
