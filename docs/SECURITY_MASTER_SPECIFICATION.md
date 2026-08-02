# 🏛️ Security Master Specification — Ticker Lifecycle & Delisting Handling

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-003`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Security Master Core Schema

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class SecurityMasterContract:
    symbol: str               # Canonical symbol e.g., "600519.SH"
    exchange: str             # "SSE", "SZSE", "BSE"
    display_name: str         # "贵州茅台"
    security_type: str        # "STOCK", "INDEX", "ETF", "OPTION"
    list_date: str            # "YYYY-MM-DD"
    delist_date: Optional[str] # "YYYY-MM-DD" or None
    status: str               # "ACTIVE", "DELISTED", "SUSPENDED"
    industry_sw_l1: str       # 申万一级行业
    industry_sw_l2: str       # 申万二级行业
```

---

## 2. Survivorship Bias Mitigation

To prevent **Survivorship Bias** in historical backtests:
- Historical asset universes are populated using `SecurityMasterContract` snapshots as of trading date $T$.
- Delisted stocks (e.g. `600001.SH` delisted in past) remain included in historical universes for trading dates prior to their delisting date.
