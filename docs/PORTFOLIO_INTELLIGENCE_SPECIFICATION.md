# 🧠 Portfolio Intelligence Specification — V2 Construction & Turnover Control

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-006B`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Portfolio Construction V2 (`PortfolioConstructorV2`)

- **Max Position Cap**: Hard cap per security weight $w_i \le \text{max\_position\_limit}$ (e.g. 20%).
- **Turnover Constraint**: Tracks daily rebalancing turnover $\text{Turnover} = \frac{1}{2} \sum |w_{i,t} - w_{i,t-1}|$. If rebalance turnover exceeds `max_turnover_limit`, trade sizes are scaled back proportionally.
- **Tradability Filtering**: Integrates `SecurityMasterRegistry` to exclude delisted or suspended securities.
