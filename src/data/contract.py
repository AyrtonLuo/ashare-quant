"""
contract.py
统一行情数据契约 (MarketDataContract) 与 Normalization 规范引擎：
1. 统一 Data Layer -> Service Layer -> UI Layer 的行情数据交互标准。
2. 自动补充缺失字段 (兼容 pickle/dataclass/dict 跨版本反序列化)，解决 AttributeError 崩溃根源。
3. 严格规范 status ("AVAILABLE" / "UNAVAILABLE"), data_mode ("RESEARCH" / "DEMO"), is_real (True / False)。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from src.data.symbol_utils import normalize_ashare_code


@dataclass
class MarketDataContract:
    symbol: str
    name: str
    market: str
    timestamp: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: float = 0.0
    amount: float = 0.0
    change_pct: float = 0.0
    status: str = "AVAILABLE"  # "AVAILABLE" 或 "UNAVAILABLE"
    source: Optional[str] = None
    data_mode: str = "RESEARCH"  # "RESEARCH" 或 "DEMO"
    is_real: bool = True
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "market": self.market,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "amount": self.amount,
            "change_pct": self.change_pct,
            "status": self.status,
            "source": self.source,
            "data_mode": self.data_mode,
            "is_real": self.is_real
        }


def normalize_market_data_contract(data_obj: Any) -> MarketDataContract:
    """
    将任意 Provider 返回的对象 (MarketData, dict, 缓存反序列化对象) 归一化为标准的 MarketDataContract
    """
    if isinstance(data_obj, MarketDataContract):
        return data_obj

    # 处理 Dict
    if isinstance(data_obj, dict):
        sym = str(data_obj.get("symbol") or data_obj.get("code") or "000001.SH")
        info = normalize_ashare_code(sym)
        close_val = data_obj.get("close") or data_obj.get("price")
        status_val = data_obj.get("status")
        if not status_val or status_val == "DATA_UNAVAILABLE":
            status_val = "UNAVAILABLE" if close_val is None else "AVAILABLE"

        return MarketDataContract(
            symbol=info["suffix"],
            name=str(data_obj.get("name") or info["name"]),
            market=info["market"],
            timestamp=data_obj.get("timestamp"),
            open=data_obj.get("open"),
            high=data_obj.get("high"),
            low=data_obj.get("low"),
            close=close_val,
            volume=float(data_obj.get("volume", 0.0)),
            amount=float(data_obj.get("amount", 0.0)),
            change_pct=float(data_obj.get("change_pct", 0.0)),
            status=status_val,
            source=data_obj.get("source"),
            data_mode=str(data_obj.get("data_mode", "RESEARCH")),
            is_real=bool(data_obj.get("is_real", True if status_val == "AVAILABLE" else False))
        )

    # 处理 MarketData 或第三方 Dataclass/Object
    sym = getattr(data_obj, "symbol", "000001.SH")
    info = normalize_ashare_code(sym)

    close_val = getattr(data_obj, "close", None)
    status_val = getattr(data_obj, "status", None)
    if not status_val or status_val == "DATA_UNAVAILABLE":
        status_val = "UNAVAILABLE" if (close_val is None or getattr(data_obj, "status", None) == "DATA_UNAVAILABLE") else "AVAILABLE"

    source_val = getattr(data_obj, "source", None)
    data_mode_val = getattr(data_obj, "data_mode", "RESEARCH")
    is_real_val = getattr(data_obj, "is_real", True if (status_val == "AVAILABLE" and data_mode_val == "RESEARCH") else False)

    return MarketDataContract(
        symbol=info["suffix"],
        name=getattr(data_obj, "name", info["name"]) or info["name"],
        market=info["market"],
        timestamp=getattr(data_obj, "timestamp", None),
        open=getattr(data_obj, "open", None),
        high=getattr(data_obj, "high", None),
        low=getattr(data_obj, "low", None),
        close=close_val,
        volume=float(getattr(data_obj, "volume", 0.0)),
        amount=float(getattr(data_obj, "amount", 0.0)),
        change_pct=float(getattr(data_obj, "change_pct", 0.0)),
        status=status_val,
        source=source_val,
        data_mode=data_mode_val,
        is_real=is_real_val
    )
