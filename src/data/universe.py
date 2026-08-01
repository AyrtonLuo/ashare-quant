"""
universe.py
Point-in-Time 历史成分股提供器接口 (HistoricalUniverseProvider)
避免幸存者偏差 (Survivorship Bias)——不允许用今日的成分股直调历史。
已知技术局限说明 (Known Limitation):
当前公开 API 主要支持静止指数成分股提取，未来扩展支持历史变动成分日志 (PIT Universe)。
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import pandas as pd


class HistoricalUniverseProvider(ABC):
    @abstractmethod
    def get_universe(self, date_str: str, index_code: str = "000300") -> List[str]:
        """
        获取指定日期 date_str 的 Point-in-Time 指数成分股列表
        """
        pass


class StaticUniverseProvider(HistoricalUniverseProvider):
    """
    默认基准成分股提供器
    """
    def __init__(self, default_symbols: Optional[List[str]] = None):
        self.default_symbols = default_symbols or ["600519", "000001", "600690", "300308", "600398"]

    def get_universe(self, date_str: str, index_code: str = "000300") -> List[str]:
        return self.default_symbols
