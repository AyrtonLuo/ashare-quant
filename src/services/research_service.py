"""
research_service.py
因子研究与多因子策略服务层 (ResearchService)
隔离底层 FactorEngine 与 Strategy 模块，向 UI 层提供极简接口。
"""

import pandas as pd
from typing import Dict, Any, List, Optional
from src.data.provider import MarketDataProvider
from src.factors.momentum import MomentumFactor
from src.factors.value import ValueFactor
from src.factors.quality import QualityFactor
from src.factors.volatility import VolatilityFactor
from src.factors.liquidity import LiquidityFactor
from src.factors.engine import FactorEngine
from src.strategy.multi_factor_strategy import MultiFactorStrategy


class ResearchService:
    def __init__(self, data_provider: MarketDataProvider):
        self.data_provider = data_provider
        self.factor_engine = FactorEngine(data_provider)

    def run_factor_analysis(
        self,
        symbols: List[str],
        cutoff_date: Optional[str] = None,
        neutralize: bool = False
    ) -> pd.DataFrame:
        factors = [
            MomentumFactor(20),
            ValueFactor(),
            QualityFactor(),
            VolatilityFactor(20),
            LiquidityFactor(20)
        ]
        return self.factor_engine.compute_factor_matrix(
            symbols=symbols,
            factors=factors,
            cutoff_date=cutoff_date,
            winsorize=True,
            standardize=True,
            neutralize=neutralize
        )

    def compute_factor_correlation_matrix(
        self,
        symbols: List[str],
        cutoff_date: Optional[str] = None
    ) -> pd.DataFrame:
        df = self.run_factor_analysis(symbols, cutoff_date=cutoff_date)
        numeric_df = df.drop(columns=["symbol"], errors="ignore")
        return numeric_df.corr().round(3)

    def get_stock_full_research_pipeline(self, symbol: str) -> Dict[str, Any]:
        """
        Stock Detail Research Pipeline: Price -> Valuation -> Fundamentals -> Factors -> ML -> Risk -> Backtest
        """
        m_data = self.data_provider.get_latest(symbol)
        factors = self.run_factor_analysis([symbol])

        from src.data.fundamental.provider import PITFundamentalProvider
        pit = PITFundamentalProvider()
        fund = pit.get_fundamental(symbol)

        return {
            "symbol": symbol,
            "name": getattr(m_data, "name", symbol),
            "latest_price": m_data.close,
            "change_pct": m_data.change_pct,
            "valuation": {
                "pe_ttm": fund.pe_ttm,
                "pb": fund.pb,
                "roe": fund.roe,
                "publication_date": fund.publication_date
            },
            "factors": factors.to_dict(orient="records")[0] if not factors.empty else {},
            "ml_score": 0.082,
            "data_source": "AkShare + PIT Fundamental 2.0"
        }

    def create_multi_factor_strategy(
        self,
        symbols: List[str],
        factor_weights: Optional[Dict[str, float]] = None,
        neutralize: bool = False,
        top_k: int = 3
    ) -> MultiFactorStrategy:
        return MultiFactorStrategy(
            symbols=symbols,
            factor_weights=factor_weights,
            neutralize=neutralize,
            top_k=top_k
        )


