# ⏱️ Data Freshness Specification — Data Age & Real-Time Classification

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-004`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Freshness Age Calculation

$$\text{data\_age} = \text{current\_time} - \text{provider\_timestamp}$$

- **REALTIME**: $\text{data\_age} \le 1.0\text{ s}$. UI Tag: `LIVE`.
- **DELAYED_REALTIME**: $1.0\text{ s} < \text{data\_age} \le 900.0\text{ s}$. UI Tag: `DELAYED`.
- **HISTORICAL**: Daily close bars. UI Tag: `HISTORICAL`.
- **CLOSED MARKET**: Outside trading hours. UI Tag: `LAST_CLOSE`.
