# ⚙️ Strategy Configuration Specification — Schema & Rebalance Calendars

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-006B`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Schema Specification (`StrategyConfig`)

- **Rebalance Frequency (`RebalanceFrequency`)**: `DAILY`, `WEEKLY`, `MONTHLY` filtered strictly using `Canonical TradingCalendar` (`RebalanceCalendarEngine`).
- **Investment Universe (`UniverseType`)**: `ALL_A_SHARE`, `CUSTOM_SYMBOLS`, `INDEX_CONSTITUENTS`.
- **Constraint Parameters**: `max_position_limit` (default 20%), `max_turnover_limit` (default 50%).
