# 📈 Corporate Action Specification — Ex-Rights & Adjustment Logic

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-002`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Corporate Action Event Types

1. **Cash Dividend (派息)**: Cash amount per share $D$.
2. **Bonus Shares (送股)**: Bonus shares ratio $B$ per share.
3. **Rights Offering (配股)**: Rights price $P_r$ and rights ratio $R$.
4. **Stock Split (拆股)**: Split ratio $S$.

---

## 2. Ex-Rights Price Adjustment Calculation

Ex-rights price $P_{\text{ex}}$ on effective date:
$$P_{\text{ex}} = \frac{P_{\text{pre}} - D + P_r \times R}{1 + B + R}$$

Backward Cumulative Adjustment Factor $F_t$:
$$F_t = \prod_{\tau > t} \left( \frac{P_{\text{pre},\tau}}{P_{\text{ex},\tau}} \right)$$

$$\text{Adjusted Price}_t = P_t \times F_t$$
