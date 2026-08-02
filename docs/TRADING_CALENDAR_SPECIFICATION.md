# 📅 Trading Calendar Specification — China A-Share Market Calendar

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-003`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Unified Trading Calendar Interface

Quant Engine and Strategy Engine **MUST NOT** compute trading days using naive weekday loops. They must query the canonical `TradingCalendar`:

```python
class TradingCalendar:
    def is_trading_day(self, date_str: str) -> bool:
        """Returns True if date_str (YYYY-MM-DD) is an official A-Share trading day."""
        pass

    def get_trading_days(self, start_date: str, end_date: str) -> list:
        """Returns list of trading dates between start_date and end_date."""
        pass

    def get_previous_trading_day(self, date_str: str) -> str:
        """Returns previous trading day string."""
        pass
```
