# 🔌 Unified Provider Interface Specification

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-003`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Unified Provider Base Interface

All data providers implement the abstract `UnifiedDataProvider` class:

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract
from src.data.contracts.corporate_action import CorporateActionContract


class UnifiedDataProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str: pass

    @property
    @abstractmethod
    def provider_version(self) -> str: pass

    @abstractmethod
    def get_security_master(self) -> List[dict]:
        """Fetches list of active and delisted A-Share securities."""
        pass

    @abstractmethod
    def get_trading_calendar(self, start_date: str, end_date: str) -> List[str]:
        """Fetches trading days for China A-Share market."""
        pass

    @abstractmethod
    def get_daily_market_data(self, symbol: str, start_date: str, end_date: str) -> List[MarketDataContract]:
        """Fetches and adapts daily bar market data."""
        pass

    @abstractmethod
    def get_fundamental_data(self, symbol: str, trade_date: str) -> Optional[FundamentalDataContract]:
        """Fetches and adapts point-in-time fundamental statement data."""
        pass

    @abstractmethod
    def get_corporate_actions(self, symbol: str, start_date: str, end_date: str) -> List[CorporateActionContract]:
        """Fetches corporate actions (dividends, splits, bonus shares)."""
        pass
```
