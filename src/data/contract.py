"""
contract.py
统一行情数据契约 (MarketDataContract) 与 Normalization 规范引擎：
1. 统一 Data Layer -> Service Layer -> UI Layer 的行情数据交互标准。
2. 采用安全分层解析 (Tiered Resolution)，绝对杜绝在 getattr 中关联可能缺失的 dict key 导致 KeyError 崩溃。
3. 集成 Canonical Symbol Registry，确保 000001.SH -> 上证指数, 000001.SZ -> 平安银行 确定解析。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from src.data.symbol_utils import normalize_ashare_code, CANONICAL_SYMBOL_NAMES


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


def get_canonical_symbol_name(symbol: str, default_name: Optional[str] = None) -> str:
    """
    确定性规范名称解析器 (Canonical Symbol Name Resolver)
    """
    info = normalize_ashare_code(symbol)
    suffix = info.get("suffix", str(symbol).strip().upper())
    name = info.get("name") or CANONICAL_SYMBOL_NAMES.get(suffix) or default_name or suffix
    return name


def normalize_market_data_contract(data_obj: Any) -> MarketDataContract:
    """
    将任意 Provider 返回的对象 (MarketData, dict, 缓存反序列化对象) 归一化为标准的 MarketDataContract。
    使用安全分层解析 (Tiered Resolution)，零 KeyError 风险。
    """
    if isinstance(data_obj, MarketDataContract):
        return data_obj

    # 1. 确定 Symbol 与解析元数据
    raw_sym = None
    if isinstance(data_obj, dict):
        raw_sym = data_obj.get("symbol") or data_obj.get("code")
    else:
        raw_sym = getattr(data_obj, "symbol", None)

    sym = str(raw_sym or "000001.SH").strip().upper()
    info = normalize_ashare_code(sym)
    suffix = info.get("suffix", sym)
    market = info.get("market", "SH")

    # 2. 安全确定名称 (Priority: data_obj.name -> info["name"] -> CANONICAL_SYMBOL_NAMES -> suffix)
    obj_name = None
    if isinstance(data_obj, dict):
        obj_name = data_obj.get("name")
    else:
        obj_name = getattr(data_obj, "name", None)

    info_name = info.get("name") or CANONICAL_SYMBOL_NAMES.get(suffix)
    resolved_name = str(obj_name or info_name or suffix)

    # 3. 安全提取价格与基础数据
    if isinstance(data_obj, dict):
        close_val = data_obj.get("close")
        if close_val is None:
            close_val = data_obj.get("price")
        status_val = data_obj.get("status")
        source_val = data_obj.get("source")
        data_mode_val = str(data_obj.get("data_mode", "RESEARCH"))
        raw_is_real = data_obj.get("is_real")
        ts_val = data_obj.get("timestamp")
        open_val = data_obj.get("open")
        high_val = data_obj.get("high")
        low_val = data_obj.get("low")
        vol_val = float(data_obj.get("volume", 0.0))
        amt_val = float(data_obj.get("amount", 0.0))
        chg_val = float(data_obj.get("change_pct", 0.0))
    else:
        close_val = getattr(data_obj, "close", None)
        status_val = getattr(data_obj, "status", None)
        source_val = getattr(data_obj, "source", None)
        data_mode_val = str(getattr(data_obj, "data_mode", "RESEARCH"))
        raw_is_real = getattr(data_obj, "is_real", None)
        ts_val = getattr(data_obj, "timestamp", None)
        open_val = getattr(data_obj, "open", None)
        high_val = getattr(data_obj, "high", None)
        low_val = getattr(data_obj, "low", None)
        vol_val = float(getattr(data_obj, "volume", 0.0))
        amt_val = float(getattr(data_obj, "amount", 0.0))
        chg_val = float(getattr(data_obj, "change_pct", 0.0))

    # 统一规范 status 与 is_real
    if close_val is None:
        status_val = "UNAVAILABLE"
    elif not status_val or status_val == "DATA_UNAVAILABLE":
        status_val = "AVAILABLE"


    if raw_is_real is not None:
        is_real_val = bool(raw_is_real)
    else:
        is_real_val = True if (status_val == "AVAILABLE" and data_mode_val == "RESEARCH") else False

    return MarketDataContract(
        symbol=suffix,
        name=resolved_name,
        market=market,
        timestamp=ts_val,
        open=open_val,
        high=high_val,
        low=low_val,
        close=close_val,
        volume=vol_val,
        amount=amt_val,
        change_pct=chg_val,
        status=status_val,
        source=source_val,
        data_mode=data_mode_val,
        is_real=is_real_val
    )
