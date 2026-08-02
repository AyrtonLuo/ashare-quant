# ⚖️ Portfolio Construction Specification — Target Weights & Constraint Validation

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-006A`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Constraint Verification

- **Total Exposure Constraint**: Enforces $\sum w_i \le 1.0$. If sum exceeds 1.0, weights are automatically re-normalized.
- **Tradability Gating**: Integrates `SecurityMasterRegistry.is_tradable_on()` to exclude suspended or delisted securities.
