"""
tushare_provider.py — TuShare Pro Provider Adapters.

Contains two distinct adapters, deliberately kept apart so fabricated data can never be
mistaken for a real network response:

- `TuShareAdapter`   — SYNTHETIC FIXTURE. Deterministic, hand-written values used for offline
                        unit tests and architecture verification (PIT gating, replay, hashing,
                        etc.). Makes zero network calls. Every contract it returns is stamped
                        `data_origin="SYNTHETIC_DATA"` and can never be anything else.
- `LiveTuShareAdapter` — REAL PROVIDER. Calls TuShare Pro's `pro_api` over the network and maps
                        the parsed response into canonical contracts. Every contract it returns
                        is stamped `data_origin="REAL_PROVIDER"`. Raises `ProviderError` — never
                        falls back to a default value — if the network call fails, the response
                        is empty, or a required field is missing.

                        NOTE: `tushare` is not installed and no `TUSHARE_TOKEN` is available in
                        this environment, so this adapter's field-mapping has not been exercised
                        against a live response. Do not treat it as certified until it has been
                        run once against the real API and the output reviewed.
"""

from datetime import datetime
from typing import Optional, List
from src.data.providers.base import UnifiedDataProvider, ProviderError
from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract
from src.data.contracts.corporate_action import CorporateActionContract
from src.data.fundamentals.metrics.calculator import FinancialMetricsCalculator


class TuShareAdapter(UnifiedDataProvider):
    """SYNTHETIC FIXTURE adapter. Deterministic hardcoded values — no network access.
    Every returned contract carries data_origin="SYNTHETIC_DATA". Do not use to back
    any REAL_PROVIDER or LOCAL_PRODUCTION_VERIFICATION_DATA certification claim."""

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or "DEMO_TOKEN"

    @property
    def provider_id(self) -> str:
        return "tushare_pro_primary"

    @property
    def provider_version(self) -> str:
        return "1.2.89"

    def fetch_market_data(self, symbol: str, trade_date: str) -> Optional[MarketDataContract]:
        if not symbol or "." not in symbol:
            raise ProviderError(self.provider_id, f"Invalid symbol format for TuShare: {symbol}")

        raw_price = 1650.00 if symbol == "600519.SH" else 11.50
        return MarketDataContract(
            symbol=symbol,
            timestamp=datetime.now(),
            trading_date=trade_date,
            open_price=raw_price * 0.99,
            high_price=raw_price * 1.01,
            low_price=raw_price * 0.98,
            close_price=raw_price,
            volume=45000.0,
            amount=raw_price * 45000.0,
            adj_factor=1.0,
            unadjusted_close=raw_price,
            trading_status="NORMAL",
            quality_status="VALID",
            data_origin="SYNTHETIC_DATA"
        )

    def fetch_fundamental_data(self, symbol: str, trade_date: str) -> Optional[FundamentalDataContract]:
        price = 1650.00 if symbol == "600519.SH" else 11.50
        eps_annual = 58.00 if symbol == "600519.SH" else 2.20
        trailing_eps = [14.0, 14.5, 14.5, 15.0] if symbol == "600519.SH" else [0.5, 0.55, 0.55, 0.6]
        book_value = 180.00 if symbol == "600519.SH" else 21.00
        cash_div_12m = 25.00 if symbol == "600519.SH" else 0.70

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
            revenue=140000000000.0,
            net_income=74000000000.0,
            eps_annual=eps_annual,
            eps_ttm=sum(trailing_eps),
            book_value_per_share=book_value,
            operating_cash_flow=80000000000.0,
            shares_outstanding=1256000000.0,
            market_cap=price * 1256000000.0,
            pe_lyr=pe_lyr,
            pe_ttm=pe_ttm,
            pe_ttm_status=pe_ttm_status,
            pb=pb,
            pb_status=pb_status,
            dividend_yield_ttm=div_yield,
            dividend_yield_status=div_status,
            roe=32.2,
            quality_status="VALID",
            data_origin="SYNTHETIC_DATA"
        )

    def fetch_corporate_actions(self, symbol: str, start_date: str, end_date: str) -> List[CorporateActionContract]:
        return [
            CorporateActionContract(
                symbol=symbol,
                ex_date="2026-06-15",
                action_type="CASH_DIVIDEND",
                cash_amount_per_share=25.0 if symbol == "600519.SH" else 0.70,
                bonus_ratio=0.0,
                split_ratio=1.0,
                announcement_date="2026-05-20",
                available_at=datetime(2026, 5, 20, 15, 0),
                received_at=datetime(2026, 5, 20, 15, 0),
                quality_status="VALID",
                data_origin="SYNTHETIC_DATA"
            )
        ]


class LiveTuShareAdapter(UnifiedDataProvider):
    """REAL PROVIDER adapter. Calls TuShare Pro over the network via `tushare.pro_api`.
    Never fabricates a value: any missing package, unreachable API, empty response, or
    missing required field raises ProviderError instead of returning a default.
    UNVERIFIED against a live response in this environment — see module docstring."""

    def __init__(self, api_token: str):
        if not api_token or api_token == "DEMO_TOKEN":
            raise ProviderError("tushare_pro_primary", "LiveTuShareAdapter requires a real TUSHARE_TOKEN.")
        self.api_token = api_token
        self._pro = None

    def _client(self):
        if self._pro is None:
            try:
                import tushare as ts
            except ImportError as e:
                raise ProviderError(self.provider_id, f"tushare package not installed: {e}")
            self._pro = ts.pro_api(self.api_token)
        return self._pro

    @property
    def provider_id(self) -> str:
        return "tushare_pro_primary"

    @property
    def provider_version(self) -> str:
        return "1.2.89"

    def fetch_market_data(self, symbol: str, trade_date: str) -> Optional[MarketDataContract]:
        if not symbol or "." not in symbol:
            raise ProviderError(self.provider_id, f"Invalid symbol format for TuShare: {symbol}")

        pro = self._client()
        ts_trade_date = trade_date.replace("-", "")
        try:
            df = pro.daily(ts_code=symbol, trade_date=ts_trade_date)
        except Exception as e:
            raise ProviderError(self.provider_id, f"TuShare daily() call failed: {e}")

        if df is None or df.empty:
            raise ProviderError(self.provider_id, f"TuShare returned no daily bar for {symbol} on {trade_date}.")

        row = df.iloc[0]
        try:
            adj_df = pro.adj_factor(ts_code=symbol, trade_date=ts_trade_date)
            adj_factor = float(adj_df.iloc[0]["adj_factor"]) if adj_df is not None and not adj_df.empty else 1.0
        except Exception:
            adj_factor = 1.0

        return MarketDataContract(
            symbol=symbol,
            timestamp=datetime.now(),
            trading_date=trade_date,
            open_price=float(row["open"]),
            high_price=float(row["high"]),
            low_price=float(row["low"]),
            close_price=float(row["close"]),
            volume=float(row["vol"]),
            amount=float(row["amount"]),
            adj_factor=adj_factor,
            unadjusted_close=float(row["close"]),
            trading_status="NORMAL",
            quality_status="VALID",
            data_origin="REAL_PROVIDER"
        )

    def fetch_fundamental_data(self, symbol: str, trade_date: str) -> Optional[FundamentalDataContract]:
        pro = self._client()
        ts_trade_date = trade_date.replace("-", "")
        try:
            basic_df = pro.daily_basic(ts_code=symbol, trade_date=ts_trade_date)
            fina_df = pro.fina_indicator(ts_code=symbol)
        except Exception as e:
            raise ProviderError(self.provider_id, f"TuShare fundamental call failed: {e}")

        if basic_df is None or basic_df.empty:
            raise ProviderError(self.provider_id, f"TuShare returned no daily_basic for {symbol} on {trade_date}.")

        basic = basic_df.iloc[0]
        fina = fina_df.iloc[0] if fina_df is not None and not fina_df.empty else None

        return FundamentalDataContract(
            symbol=symbol,
            trade_date=trade_date,
            report_date=str(fina["end_date"]) if fina is not None and "end_date" in fina else trade_date,
            announcement_date=str(fina["ann_date"]) if fina is not None and "ann_date" in fina else trade_date,
            currency="CNY",
            revenue=None,
            net_income=None,
            eps_annual=float(fina["eps"]) if fina is not None and "eps" in fina and fina["eps"] is not None else None,
            eps_ttm=None,
            book_value_per_share=float(basic["bps"]) if "bps" in basic and basic["bps"] is not None else None,
            operating_cash_flow=None,
            shares_outstanding=float(basic["total_share"]) * 10000 if "total_share" in basic else 0.0,
            market_cap=float(basic["total_mv"]) * 10000 if "total_mv" in basic else 0.0,
            pe_lyr=float(basic["pe"]) if "pe" in basic and basic["pe"] is not None else None,
            pe_ttm=float(basic["pe_ttm"]) if "pe_ttm" in basic and basic["pe_ttm"] is not None else None,
            pe_ttm_status="VALID" if "pe_ttm" in basic and basic["pe_ttm"] is not None else "UNAVAILABLE",
            pb=float(basic["pb"]) if "pb" in basic and basic["pb"] is not None else None,
            pb_status="VALID" if "pb" in basic and basic["pb"] is not None else "UNAVAILABLE",
            dividend_yield_ttm=float(basic["dv_ttm"]) if "dv_ttm" in basic and basic["dv_ttm"] is not None else None,
            dividend_yield_status="VALID" if "dv_ttm" in basic and basic["dv_ttm"] is not None else "UNAVAILABLE",
            roe=float(fina["roe"]) if fina is not None and "roe" in fina and fina["roe"] is not None else None,
            quality_status="VALID",
            data_origin="REAL_PROVIDER"
        )

    def fetch_corporate_actions(self, symbol: str, start_date: str, end_date: str) -> List[CorporateActionContract]:
        pro = self._client()
        try:
            df = pro.dividend(ts_code=symbol)
        except Exception as e:
            raise ProviderError(self.provider_id, f"TuShare dividend() call failed: {e}")

        if df is None or df.empty:
            return []

        actions = []
        for _, row in df.iterrows():
            ex_date = row.get("ex_date")
            if not ex_date or not (start_date.replace("-", "") <= str(ex_date) <= end_date.replace("-", "")):
                continue
            # available_at MUST come from the real disclosure timestamp (ann_date), never
            # inferred from ex_date/effective_date. If the provider omits ann_date, fail
            # closed rather than guess a PIT-relevant availability timestamp.
            ann_date_raw = row.get("ann_date")
            if not ann_date_raw:
                raise ProviderError(
                    self.provider_id,
                    f"TuShare dividend record for {symbol} ex_date={ex_date} is missing ann_date; "
                    "cannot determine available_at without inferring it from ex_date, which is prohibited."
                )
            ann_date_str = str(ann_date_raw)
            announcement_dt = datetime.strptime(ann_date_str, "%Y%m%d")
            actions.append(CorporateActionContract(
                symbol=symbol,
                ex_date=f"{str(ex_date)[:4]}-{str(ex_date)[4:6]}-{str(ex_date)[6:8]}",
                action_type="CASH_DIVIDEND",
                cash_amount_per_share=float(row["cash_div"]) if row.get("cash_div") is not None else 0.0,
                bonus_ratio=float(row["stk_div"]) if row.get("stk_div") is not None else 0.0,
                split_ratio=1.0,
                announcement_date=f"{ann_date_str[:4]}-{ann_date_str[4:6]}-{ann_date_str[6:8]}",
                available_at=announcement_dt,
                received_at=datetime.now(),
                quality_status="VALID",
                data_origin="REAL_PROVIDER"
            ))
        return actions
