"""
akshare_provider.py — AkShare Provider Adapters.

Mirrors tushare_provider.py's split: `AkShareProviderAdapter` is a SYNTHETIC FIXTURE (no network
access, always data_origin="SYNTHETIC_DATA"); `LiveAkShareProviderAdapter` is the REAL PROVIDER
adapter that calls the `akshare` package and stamps data_origin="REAL_PROVIDER" only on values it
actually parsed from a live response. `akshare` is not installed in this environment, so the live
adapter's field-mapping has not been exercised against a real response — treat it as unverified
until run once against the real package and reviewed.
"""

from datetime import datetime
from typing import Optional
from src.data.providers.base import UnifiedDataProvider, ProviderError
from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract
from src.data.contracts.corporate_action import CorporateActionContract
from src.data.fundamentals.metrics.calculator import FinancialMetricsCalculator


class AkShareProviderAdapter(UnifiedDataProvider):
    """SYNTHETIC FIXTURE adapter. Deterministic hardcoded values — no network access.
    Every returned contract carries data_origin="SYNTHETIC_DATA". Do not use to back
    any REAL_PROVIDER or LOCAL_PRODUCTION_VERIFICATION_DATA certification claim."""

    @property
    def provider_id(self) -> str:
        return "akshare_primary"

    @property
    def provider_version(self) -> str:
        return "1.12.0"

    def fetch_market_data(self, symbol: str, trade_date: str) -> Optional[MarketDataContract]:
        # Simulated raw values for demonstration & testing
        raw_price = 1650.00 if symbol == "600519.SH" else 12.50
        return MarketDataContract(
            symbol=symbol,
            timestamp=datetime.now(),
            trading_date=trade_date,
            open_price=raw_price * 0.99,
            high_price=raw_price * 1.02,
            low_price=raw_price * 0.98,
            close_price=raw_price,
            volume=50000.0,
            amount=raw_price * 50000.0,
            adj_factor=1.0,
            unadjusted_close=raw_price,
            trading_status="NORMAL",
            quality_status="VALID",
            data_origin="SYNTHETIC_DATA"
        )

    def fetch_fundamental_data(self, symbol: str, trade_date: str) -> Optional[FundamentalDataContract]:
        price = 1650.00 if symbol == "600519.SH" else 12.50
        eps_annual = 58.00 if symbol == "600519.SH" else -0.50
        trailing_eps = [14.0, 14.5, 14.5, 15.0] if symbol == "600519.SH" else [-0.1, -0.1, -0.15, -0.15]
        book_value = 180.00 if symbol == "600519.SH" else 5.00
        cash_div_12m = 25.00 if symbol == "600519.SH" else 0.00

        pe_lyr, pe_status = FinancialMetricsCalculator.calculate_pe_lyr(price, eps_annual)
        pe_ttm, pe_ttm_status = FinancialMetricsCalculator.calculate_pe_ttm(price, trailing_eps)
        pb, pb_status = FinancialMetricsCalculator.calculate_pb(price, book_value)
        div_yield, div_status = FinancialMetricsCalculator.calculate_dividend_yield_ttm(price, cash_div_12m)

        return FundamentalDataContract(
            symbol=symbol,
            trade_date=trade_date,
            report_date="2025-12-31",
            announcement_date="2026-03-31",
            currency="CNY",
            revenue=140000000000.0 if symbol == "600519.SH" else 500000000.0,
            net_income=74000000000.0 if symbol == "600519.SH" else -100000000.0,
            eps_annual=eps_annual,
            eps_ttm=sum(trailing_eps),
            book_value_per_share=book_value,
            operating_cash_flow=80000000000.0 if symbol == "600519.SH" else 10000000.0,
            shares_outstanding=1256000000.0,
            market_cap=price * 1256000000.0,
            pe_lyr=pe_lyr,
            pe_ttm=pe_ttm,
            pe_ttm_status=pe_ttm_status,
            pb=pb,
            pb_status=pb_status,
            dividend_yield_ttm=div_yield,
            dividend_yield_status=div_status,
            roe=32.2 if symbol == "600519.SH" else -10.0,
            quality_status="VALID",
            data_origin="SYNTHETIC_DATA"
        )

    def fetch_corporate_actions(self, symbol: str, start_date: str, end_date: str) -> list:
        return [
            CorporateActionContract(
                symbol=symbol,
                ex_date="2026-06-15",
                action_type="CASH_DIVIDEND",
                cash_amount_per_share=25.0 if symbol == "600519.SH" else 0.0,
                bonus_ratio=0.0,
                split_ratio=1.0,
                announcement_date="2026-05-20",
                available_at=datetime(2026, 5, 20, 15, 0),
                received_at=datetime(2026, 5, 20, 15, 0),
                quality_status="VALID",
                data_origin="SYNTHETIC_DATA"
            )
        ]


class LiveAkShareProviderAdapter(UnifiedDataProvider):
    """REAL PROVIDER adapter. Calls the `akshare` package over the network.
    Never fabricates a value: any missing package, unreachable source, empty response, or
    missing required field raises ProviderError instead of returning a default.
    UNVERIFIED against a live response in this environment — see module docstring."""

    def _client(self):
        try:
            import akshare as ak
        except ImportError as e:
            raise ProviderError(self.provider_id, f"akshare package not installed: {e}")
        return ak

    @property
    def provider_id(self) -> str:
        return "akshare_secondary"

    @property
    def provider_version(self) -> str:
        return "1.12.0"

    def fetch_market_data(self, symbol: str, trade_date: str) -> Optional[MarketDataContract]:
        ak = self._client()
        ak_symbol = symbol.split(".")[0]
        ak_date = trade_date.replace("-", "")
        try:
            df = ak.stock_zh_a_hist(symbol=ak_symbol, start_date=ak_date, end_date=ak_date, adjust="")
        except Exception as e:
            raise ProviderError(self.provider_id, f"AkShare stock_zh_a_hist() call failed: {e}")

        if df is None or df.empty:
            raise ProviderError(self.provider_id, f"AkShare returned no daily bar for {symbol} on {trade_date}.")

        row = df.iloc[0]
        return MarketDataContract(
            symbol=symbol,
            timestamp=datetime.now(),
            trading_date=trade_date,
            open_price=float(row["开盘"]),
            high_price=float(row["最高"]),
            low_price=float(row["最低"]),
            close_price=float(row["收盘"]),
            volume=float(row["成交量"]),
            amount=float(row["成交额"]),
            adj_factor=1.0,
            unadjusted_close=float(row["收盘"]),
            trading_status="NORMAL",
            quality_status="VALID",
            data_origin="REAL_PROVIDER"
        )

    def fetch_fundamental_data(self, symbol: str, trade_date: str) -> Optional[FundamentalDataContract]:
        raise ProviderError(self.provider_id, "LiveAkShareProviderAdapter.fetch_fundamental_data is not yet implemented against a verified real akshare response.")

    def fetch_corporate_actions(self, symbol: str, start_date: str, end_date: str) -> list:
        raise ProviderError(self.provider_id, "LiveAkShareProviderAdapter.fetch_corporate_actions is not yet implemented against a verified real akshare response.")
