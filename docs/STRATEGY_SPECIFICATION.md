# 📈 Strategy Specification — Simple Momentum Strategy

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-006A`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Simple Momentum Strategy Rules

- **Signal Selection**: Filters top $N$ securities with `BUY_BIAS` signal recommendations.
- **Weight Assignment**: Equal-weight target allocation across selected top $N$ securities.
- **Deterministic Requirement**: 100% rule-based execution. Zero LLM intervention during backtesting.
