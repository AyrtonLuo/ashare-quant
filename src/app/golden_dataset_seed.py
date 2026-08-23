"""
golden_dataset_seed.py — Deterministic GOLDEN_DATASET seed for the Phase 8R Research Workbench.

Phase 7I found the real repository's data/research/ directory empty — no dataset has ever been
persisted to disk anywhere in this project. Phase 8R's UI needs something to actually run a
certified research run against, without TUSHARE_TOKEN and without fabricating REAL_PROVIDER
data. This module generates a small, fully deterministic, explicitly GOLDEN_DATASET-tagged
price/fundamental/corporate-action dataset and persists it exactly the way a real dataset
would be: real Parquet files via ParquetStorageAdapter, a real byte-level SHA-256 manifest via
PersistentDatasetManifestManager, certified into a disk-backed PersistentDatasetManifestStore
under data/manifests/ (gitignored — never committed, matching this project's established rule
against committing binary datasets to git).

Regenerating is idempotent: the same symbols/dates/prices always hash to the same
content_sha256, so calling ensure_golden_dataset() at every app startup is a harmless no-op
once the dataset already exists on disk with matching content — and a hard failure (via
PersistentDatasetManifestStore's existing immutability check) if the on-disk bytes were ever
tampered with, exactly like any other Phase 7I-certified dataset.

Nothing here is claimed to be REAL_PROVIDER, live, or TuShare-sourced. Every contract
constructed by this module carries data_origin="GOLDEN_DATASET" explicitly.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from src.data.contracts.market_data import MarketDataContract
from src.data.contracts.fundamental_data import FundamentalDataContract, MetricProvenance
from src.data.contracts.corporate_action import CorporateActionContract
from src.data.storage.parquet_adapter import ParquetStorageAdapter
from src.data.domain.persistent_manifest import (
    PersistentDatasetManifestManager,
    PersistentDatasetManifestStore,
    PersistentDatasetManifest,
)
from src.data.domain.security_master import SecurityMasterRegistry, SecurityMasterContract
from src.data.revision.corporate_action_store import CorporateActionStore

DATASET_ID = "ds_golden_workbench_v1"
DATASET_VERSION = "v1"
DATA_ORIGIN = "GOLDEN_DATASET"

SYMBOL_DISPLAY_NAMES = {
    "600519.SH": "贵州茅台 (GOLDEN_DATASET demo)",
    "000001.SZ": "平安银行 (GOLDEN_DATASET demo)",
    "000002.SZ": "万科A (GOLDEN_DATASET demo)",
    "000333.SZ": "美的集团 (GOLDEN_DATASET demo)",
}
SYMBOLS = list(SYMBOL_DISPLAY_NAMES.keys())

# Deterministic daily trend/base per symbol — chosen so Momentum genuinely ranks them
# differently (a real risk with a uniform-trend fixture: if every symbol moved identically,
# the workbench would look "broken" — flat/no differentiation).
_BASE_PRICE = {"600519.SH": 1600.0, "000001.SZ": 12.0, "000002.SZ": 8.0, "000333.SZ": 55.0}
_DAILY_TREND = {"600519.SH": 0.006, "000001.SZ": -0.004, "000002.SZ": 0.001, "000333.SZ": 0.003}

# PE_TTM per symbol — deliberately varied so Value ranks them differently from Momentum.
_PE_TTM = {"600519.SH": 35.0, "000001.SZ": 6.5, "000002.SZ": 12.0, "000333.SZ": 18.0}

_FUNDAMENTAL_ANNOUNCEMENT_DATE = datetime(2023, 12, 1)

_N_TRADING_DAYS = 25
_FIRST_DATE = datetime(2024, 1, 2)  # a Tuesday


def _generate_trading_dates(n: int, start: datetime) -> List[datetime]:
    dates = []
    d = start
    while len(dates) < n:
        if d.weekday() < 5:  # Mon-Fri
            dates.append(d)
        d = d + timedelta(days=1)
    return dates


TRADING_DATES: List[datetime] = _generate_trading_dates(_N_TRADING_DAYS, _FIRST_DATE)
TRADING_DATE_STRS: List[str] = [d.strftime("%Y-%m-%d") for d in TRADING_DATES]


def _generate_prices(symbol: str) -> List[float]:
    base = _BASE_PRICE[symbol]
    trend = _DAILY_TREND[symbol]
    prices = []
    for i in range(_N_TRADING_DAYS):
        # Small deterministic wiggle on top of the trend so the series isn't perfectly smooth
        # (a smooth series is an unrealistic edge case for realized-volatility-style factors).
        wiggle = 0.004 * ((i % 3) - 1)
        price = base * (1.0 + trend * i + wiggle)
        prices.append(round(price, 2))
    return prices


PRICES_BY_SYMBOL: Dict[str, List[float]] = {s: _generate_prices(s) for s in SYMBOLS}

# One demonstrative corporate action, so the workbench's Corporate Action Adjustment step has
# something real to show — a cash dividend on 000333.SZ partway through the price window.
DEMO_DIVIDEND = CorporateActionContract(
    symbol="000333.SZ", ex_date=TRADING_DATE_STRS[15], action_type="CASH_DIVIDEND",
    cash_amount_per_share=0.5, bonus_ratio=0.0, split_ratio=1.0,
    announcement_date=TRADING_DATE_STRS[10],
    available_at=TRADING_DATES[10], received_at=TRADING_DATES[10],
    quality_status="VALID", data_origin=DATA_ORIGIN,
)


@dataclass(frozen=True)
class GoldenDatasetInfo:
    dataset_id: str
    dataset_version: str
    directory: str
    manifest: PersistentDatasetManifest
    symbols: List[str]
    first_date: str
    last_date: str


def _market_contracts() -> List[MarketDataContract]:
    contracts = []
    for symbol in SYMBOLS:
        prices = PRICES_BY_SYMBOL[symbol]
        for i, (date, price) in enumerate(zip(TRADING_DATES, prices)):
            contracts.append(MarketDataContract(
                symbol=symbol, timestamp=date, trading_date=TRADING_DATE_STRS[i],
                open_price=price, high_price=round(price * 1.01, 2), low_price=round(price * 0.99, 2),
                close_price=price, volume=1_000_000.0, amount=price * 1_000_000.0,
                adj_factor=1.0, unadjusted_close=price, trading_status="NORMAL",
                quality_status="VALID", data_origin=DATA_ORIGIN,
            ))
    return contracts


def market_data() -> List[MarketDataContract]:
    """Public accessor for the GOLDEN_DATASET market contracts, so the Application Layer can
    read the same series the certified dataset was built from without re-declaring how a
    contract is constructed (a second construction site could drift from this one)."""
    return _market_contracts()


def fundamental_data() -> Dict[str, List[FundamentalDataContract]]:
    """Returns the GOLDEN_DATASET fundamental records used by value_pe:v1 in the workbench."""
    result = {}
    for symbol, pe in _PE_TTM.items():
        result[symbol] = [FundamentalDataContract(
            symbol=symbol, trade_date=TRADING_DATE_STRS[0], report_date="2023-09-30",
            announcement_date=_FUNDAMENTAL_ANNOUNCEMENT_DATE.strftime("%Y-%m-%d"),
            currency="CNY", revenue=None, net_income=None, eps_annual=None, eps_ttm=None,
            book_value_per_share=None, operating_cash_flow=None,
            shares_outstanding=1e9, market_cap=pe * 1e9,
            pe_lyr=None, pe_ttm=pe, pe_ttm_status="VALID", pb=None, pb_status="UNAVAILABLE",
            dividend_yield_ttm=None, dividend_yield_status="UNAVAILABLE", roe=None,
            provenance=MetricProvenance.PROVIDER_REPORTED, quality_status="VALID",
            available_at=_FUNDAMENTAL_ANNOUNCEMENT_DATE, received_at=_FUNDAMENTAL_ANNOUNCEMENT_DATE,
            as_of=None, data_origin=DATA_ORIGIN,
        )]
    return result


def build_security_master() -> SecurityMasterRegistry:
    registry = SecurityMasterRegistry()
    for symbol, display_name in SYMBOL_DISPLAY_NAMES.items():
        registry.register(SecurityMasterContract(
            symbol=symbol, exchange="SSE" if symbol.endswith(".SH") else "SZSE",
            display_name=display_name, security_type="STOCK",
            list_date="2000-01-01", delist_date=None, status="ACTIVE",
            industry_sw_l1="GOLDEN_DATASET_DEMO", industry_sw_l2="GOLDEN_DATASET_DEMO",
        ))
    return registry


def build_corporate_action_store() -> CorporateActionStore:
    store = CorporateActionStore()
    store.add_action(DEMO_DIVIDEND)
    return store


def ensure_golden_dataset(
    research_base_dir: str = "data/research", manifest_base_dir: str = "data/manifests",
) -> GoldenDatasetInfo:
    """Idempotently materializes the GOLDEN_DATASET Parquet files on disk and certifies its
    manifest. Safe to call on every app startup — a second call with identical content is a
    no-op; if the on-disk bytes were ever tampered with, PersistentDatasetManifestStore's
    existing immutability check (Phase 7I/7J) raises FAIL CLOSED rather than silently
    re-certifying different content under the same dataset_version."""
    adapter = ParquetStorageAdapter(base_dir=research_base_dir)
    adapter.save_market_data(DATASET_ID, _market_contracts())

    directory = str(Path(research_base_dir) / DATASET_ID)
    manifest_store = PersistentDatasetManifestStore(base_dir=manifest_base_dir)
    manifest = PersistentDatasetManifestManager.build_manifest(
        DATASET_ID, DATASET_VERSION, directory, created_at=_FUNDAMENTAL_ANNOUNCEMENT_DATE.isoformat(),
    )
    manifest_store.certify(manifest)

    return GoldenDatasetInfo(
        dataset_id=DATASET_ID, dataset_version=DATASET_VERSION, directory=directory,
        manifest=manifest, symbols=SYMBOLS,
        first_date=TRADING_DATE_STRS[0], last_date=TRADING_DATE_STRS[-1],
    )
