"""
contract.py
统一行情数据契约 (MarketDataContract) 与 Normalization 规范引擎：
1. 统一 Data Layer -> Service Layer -> UI Layer 的行情数据交互标准。
2. 采用安全分层解析 (Tiered Resolution)，绝对杜绝在 getattr 中关联可能缺失的 dict key 导致 KeyError 崩溃。
3. 集成 Canonical Symbol Registry，确保 000001.SH -> 上证指数, 000001.SZ -> 平安银行 确定解析。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List
import hashlib
import pandas as pd

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


def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
    """极其安全的通用字段提取器，防护 KeyError / AttributeError / TypeError"""
    if obj is None:
        return default

    # 1. 优先属性提取
    try:
        if hasattr(obj, key):
            val = getattr(obj, key, None)
            if val is not None:
                return val
    except Exception:
        pass

    # 2. dict / mapping .get() 提取
    try:
        if isinstance(obj, dict):
            val = obj.get(key)
            if val is not None:
                return val
    except Exception:
        pass

    # 3. get 方法提取
    try:
        if hasattr(obj, "get") and callable(getattr(obj, "get")):
            val = obj.get(key, default)
            if val is not None:
                return val
    except Exception:
        pass

    # 4. __getitem__ 索引提取
    try:
        if hasattr(obj, "__getitem__"):
            val = obj[key]
            if val is not None:
                return val
    except Exception:
        pass

    return default


def _safe_float(val: Any, default: float = 0.0) -> float:
    """安全的 float 转换器，防御 None / NaN / 无效字符串"""
    if val is None:
        return default
    try:
        f = float(val)
        return default if (f != f) else f
    except (ValueError, TypeError):
        return default


def normalize_market_data_contract(data_obj: Any) -> MarketDataContract:
    """
    将任意 Provider 返回的对象 (MarketData, dict, 缓存反序列化对象) 归一化为标准的 MarketDataContract。
    使用全防御 Tiered Resolution，零 KeyError / AttributeError 风险。
    """
    if isinstance(data_obj, MarketDataContract):
        return data_obj

    # 1. 确定 Symbol 与解析元数据
    raw_sym = _safe_get(data_obj, "symbol") or _safe_get(data_obj, "code")
    sym = str(raw_sym or "000001.SH").strip().upper()
    info = normalize_ashare_code(sym)
    suffix = info.get("suffix", sym)
    market = info.get("market", "SH")

    # 2. 安全确定名称 (Priority: data_obj.name -> info["name"] -> CANONICAL_SYMBOL_NAMES -> suffix)
    obj_name = _safe_get(data_obj, "name")
    info_name = info.get("name") or CANONICAL_SYMBOL_NAMES.get(suffix)
    resolved_name = str(obj_name or info_name or suffix)

    # 3. 安全提取价格与基础数据
    close_val = _safe_get(data_obj, "close")
    if close_val is None:
        close_val = _safe_get(data_obj, "price")

    if close_val is not None:
        try:
            f_close = float(close_val)
            if f_close != f_close:  # NaN check
                close_val = None
        except (ValueError, TypeError):
            close_val = None

    status_val = _safe_get(data_obj, "status")
    source_val = _safe_get(data_obj, "source")
    data_mode_val = str(_safe_get(data_obj, "data_mode", "RESEARCH"))
    raw_is_real = _safe_get(data_obj, "is_real")
    ts_val = _safe_get(data_obj, "timestamp")
    open_val = _safe_get(data_obj, "open")
    high_val = _safe_get(data_obj, "high")
    low_val = _safe_get(data_obj, "low")

    vol_val = _safe_float(_safe_get(data_obj, "volume"), 0.0)
    amt_val = _safe_float(_safe_get(data_obj, "amount"), 0.0)
    chg_val = _safe_float(_safe_get(data_obj, "change_pct"), 0.0)

    # 4. 统一规范 status 与 is_real
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


class ErrorStatus(str, Enum):
    """全平台统一错误状态枚举"""
    AVAILABLE = "AVAILABLE"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    INVALID_SYMBOL = "INVALID_SYMBOL"
    INVALID_DATE = "INVALID_DATE"
    PIT_REJECTED = "PIT_REJECTED"
    SOURCE_ERROR = "SOURCE_ERROR"
    CALCULATION_ERROR = "CALCULATION_ERROR"


@dataclass
class FundamentalDataContract:
    """全平台统一基本面数据契约 (FundamentalDataContract)"""
    symbol: str
    trading_date: str
    fiscal_period: str
    publication_date: str
    effective_date: str
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    roe: Optional[float] = None
    eps: Optional[float] = None
    revenue: Optional[float] = None
    net_profit: Optional[float] = None
    source: str = "PIT Fundamental Provider"
    status: str = ErrorStatus.AVAILABLE.value
    is_real: bool = True
    data_mode: str = "RESEARCH"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "trading_date": self.trading_date,
            "fiscal_period": self.fiscal_period,
            "publication_date": self.publication_date,
            "effective_date": self.effective_date,
            "pe_ttm": self.pe_ttm,
            "pb": self.pb,
            "roe": self.roe,
            "eps": self.eps,
            "revenue": self.revenue,
            "net_profit": self.net_profit,
            "source": self.source,
            "status": self.status,
            "is_real": self.is_real,
            "data_mode": self.data_mode
        }


@dataclass
class MLFeatureContract:
    """全平台统一 ML 特征契约 (MLFeatureContract)"""
    symbol: str
    feature_timestamp: str
    feature_names: List[str]
    feature_values: List[float]
    source: str = "FactorEngine"
    status: str = ErrorStatus.AVAILABLE.value
    is_real: bool = True
    data_mode: str = "RESEARCH"


@dataclass
class PredictionContract:
    """全平台统一 ML 预测输出契约 (PredictionContract)"""
    symbol: str
    model_name: str
    model_version: str
    prediction_timestamp: str
    feature_timestamp: str
    prediction: float
    feature_names: List[str] = field(default_factory=list)
    source: str = "MLModel"
    status: str = ErrorStatus.AVAILABLE.value
    is_real: bool = True
    data_mode: str = "RESEARCH"


@dataclass
class HistoricalMarketDataContract:
    """全平台统一历史行情数据契约 (HistoricalMarketDataContract)"""
    symbol: str
    start_date: str
    end_date: str
    adjust: str = "qfq"
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    status: str = ErrorStatus.AVAILABLE.value
    source: str = "MarketDataProvider"
    data_mode: str = "RESEARCH"
    is_real: bool = True


class CrossSourceStatus(str, Enum):
    """跨数据源交叉验证状态"""
    EXACT_MATCH = "EXACT_MATCH"
    ACCEPTABLE_DIFFERENCE = "ACCEPTABLE_DIFFERENCE"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"


@dataclass
class ExternalDataEvidenceRecord:
    """外部真实 API 数据对账存证卡片 (ExternalDataEvidenceRecord)"""
    symbol: str
    provider: str
    provider_symbol: str
    field: str
    raw_value: Any
    normalized_value: Any
    trading_date: str
    fetch_timestamp: str
    source: str
    data_mode: str = "RESEARCH"
    is_real: bool = True
    cross_source_status: str = CrossSourceStatus.EXACT_MATCH.value
    evidence_hash: str = ""

    def __post_init__(self):
        if not self.evidence_hash:
            raw_str = f"{self.symbol}|{self.provider}|{self.field}|{self.raw_value}|{self.normalized_value}|{self.trading_date}"
            self.evidence_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "provider": self.provider,
            "provider_symbol": self.provider_symbol,
            "field": self.field,
            "raw_value": self.raw_value,
            "normalized_value": self.normalized_value,
            "trading_date": self.trading_date,
            "fetch_timestamp": self.fetch_timestamp,
            "source": self.source,
            "data_mode": self.data_mode,
            "is_real": self.is_real,
            "cross_source_status": self.cross_source_status,
            "evidence_hash": self.evidence_hash
        }




