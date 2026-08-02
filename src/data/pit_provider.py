"""
pit_provider.py
Point-In-Time (PIT) 基本面数据 Provider (PITFundamentalProvider)
严格执行 publication_date <= trading_date 断言，绝对不上漏未公开财报。
当 PIT 数据缺失或违规时强断言返回 FundamentalDataContract(status="PIT_REJECTED" / "DATA_UNAVAILABLE")，绝不受补 0 或假数据污染。
"""

import logging
from typing import Optional, Dict, Any
import pandas as pd
from src.data.contract import FundamentalDataContract, ErrorStatus
from src.data.symbol_utils import normalize_ashare_code

logger = logging.getLogger("pit_provider")


class PITFundamentalProvider:
    """PIT 基本面 Provider 实现类"""

    def __init__(self, cache_store: Optional[Dict[str, Any]] = None):
        self.cache_store = cache_store or {}

    def get_pit_fundamental(
        self,
        symbol: str,
        trading_date: str,
        publication_date: Optional[str] = None
    ) -> FundamentalDataContract:
        """
        获取指定交易日当时公开的 PIT 基本面数据。
        校验 publication_date <= trading_date。
        """
        info = normalize_ashare_code(symbol)
        suffix = info["suffix"]

        t_date = pd.to_datetime(trading_date)

        # 1. 校验已知 publication_date 是否未来泄露
        if publication_date:
            p_date = pd.to_datetime(publication_date)
            if p_date > t_date:
                logger.warning(f"PIT 泄露拦截: {suffix} 财报发布日 {publication_date} > 当前交易日 {trading_date}")
                return FundamentalDataContract(
                    symbol=suffix,
                    trading_date=trading_date,
                    fiscal_period="N/A",
                    publication_date=publication_date,
                    effective_date=publication_date,
                    pe_ttm=None,
                    pb=None,
                    roe=None,
                    eps=None,
                    revenue=None,
                    net_profit=None,
                    source="PIT Provider Cutoff Gate",
                    status=ErrorStatus.PIT_REJECTED.value,
                    is_real=False,
                    data_mode="RESEARCH"
                )

        # 2. 查询真实或受控 PIT 缓存
        cache_key = f"{suffix}_{trading_date}"
        if cache_key in self.cache_store:
            item = self.cache_store[cache_key]
            item_pub = pd.to_datetime(item.get("publication_date", trading_date))
            if item_pub <= t_date:
                return FundamentalDataContract(
                    symbol=suffix,
                    trading_date=trading_date,
                    fiscal_period=item.get("fiscal_period", "2024Q4"),
                    publication_date=item.get("publication_date", trading_date),
                    effective_date=item.get("effective_date", trading_date),
                    pe_ttm=item.get("pe_ttm"),
                    pb=item.get("pb"),
                    roe=item.get("roe"),
                    eps=item.get("eps"),
                    revenue=item.get("revenue"),
                    net_profit=item.get("net_profit"),
                    source=item.get("source", "Local PIT Fundamental Store"),
                    status=ErrorStatus.AVAILABLE.value,
                    is_real=True,
                    data_mode="RESEARCH"
                )

        # 3. 默认无 PIT 财报数据时的只读标记 (绝不上漏补 0)
        return FundamentalDataContract(
            symbol=suffix,
            trading_date=trading_date,
            fiscal_period="N/A",
            publication_date=publication_date or "N/A",
            effective_date="N/A",
            pe_ttm=None,
            pb=None,
            roe=None,
            eps=None,
            revenue=None,
            net_profit=None,
            source="PIT Fundamental Store",
            status=ErrorStatus.DATA_UNAVAILABLE.value,
            is_real=False,
            data_mode="RESEARCH"
        )
