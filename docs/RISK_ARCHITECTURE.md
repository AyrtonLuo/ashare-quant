# 🛡️ Risk Architecture — Independent Risk Engine

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-001`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Independent Risk Engine Principles

The **Risk Engine** operates as an independent gatekeeper between Strategy/Signal generation and Portfolio Execution. No trading signal or order can bypass the Risk Engine.

```text
Strategy Signal -> Risk Engine Verification -> [APPROVED] -> Execution Simulation / Order
                                   │
                                   └─────────> [REJECTED] -> Alert / Audit Log
```

---

## 2. Mandatory Risk Controls & Limit Matrix

| Risk Limit Category | Threshold Parameter | Enforcement Action |
| :--- | :--- | :--- |
| **Single Stock Weight Limit** | Max 10% of total portfolio value | Orders exceeding 10% are capped/rejected |
| **Industry Exposure Limit** | Max 30% in any single ShenWan L1 sector | Sector rebalancing enforced |
| **Daily Portfolio Drawdown** | Max 3% daily portfolio loss | Trading halted, alert emitted |
| **Max Cumulative Drawdown** | Max 15% peak-to-trough drawdown | De-leverage to cash (Risk-Off mode) |
| **Liquidity / Volume Limit** | Order volume $\le 5\%$ of 20-day ADV | Volume capped to prevent market impact |
| **Turnover Rate Limit** | Max 50% weekly portfolio turnover | Order frequency rate-limited |

---

## 3. Order Verification Flow

```python
class RiskEngine:
    def validate_order(self, order: Order, portfolio: PortfolioState) -> RiskCheckResult:
        # 1. Check single stock position limit
        if self._exceeds_stock_limit(order, portfolio):
            return RiskCheckResult(approved=False, reason="SINGLE_STOCK_LIMIT_EXCEEDED")
            
        # 2. Check sector concentration limit
        if self._exceeds_sector_limit(order, portfolio):
            return RiskCheckResult(approved=False, reason="SECTOR_EXPOSURE_LIMIT_EXCEEDED")
            
        # 3. Check daily drawdown circuit breaker
        if portfolio.daily_drawdown > 0.03:
            return RiskCheckResult(approved=False, reason="DAILY_DRAWDOWN_CIRCUIT_BREAKER")
            
        return RiskCheckResult(approved=True, reason="PASSED")
```
