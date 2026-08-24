"""
terminal_application.py — Application Layer for Terminal mode (Terminal directive step T2).

Terminal mode is the consumer-facing view: 搜索股票 → 行情 → AI 总结 → 技术面 → 基本面 →
新闻 → 风险 → 看多/看空. It is a SECOND consumer of the same certified data layer that Research
mode uses; nothing in the PIT/backtest/replay/factor core is modified or bypassed.

Three rules this module exists to enforce
=========================================
1. **The vocabulary changes, the guarantees do not.** A Terminal user never sees PIT, Evidence
   ID, hash, research identity or provider contract. Behind every panel the same
   DataTrustGate validation, the same Evidence Layer and the same citation validator still run,
   and an AI narrative that cites something it was not given still fails closed.
2. **Missing data is shown as 暂无数据, never estimated.** Every fundamental row carries an
   explicit reason for its absence, so "no number" is always distinguishable from "zero".
3. **Demo data announces itself.** `QuoteContract.is_demo` is derived from `data_origin`, so the
   DEMO DATA badge is driven by the data rather than by a UI flag that could be forgotten.

The plain-language technical readings are produced by DETERMINISTIC CODE in this module, not by
an LLM. They are descriptive statements about a number that was already computed
(`RSI 74.2 → 偏高`), never advice and never a verdict — see `_TECHNICAL_RULES`.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.app.golden_dataset_seed import (
    SYMBOL_DISPLAY_NAMES,
    DATA_ORIGIN as GOLDEN_DATA_ORIGIN,
    fundamental_data as golden_fundamental_data,
    market_data as golden_market_data,
)
from src.app import research_analyst_application as analyst
from src.data.contracts.quote import QuoteContract
from src.data.providers.base import ProviderError
from src.data.providers.fundamental_provider import (
    GoldenFundamentalProvider,
    FundamentalProvider,
    REPORT_PERIOD_NOT_DISCLOSED,
)
from src.data.providers.tencent_fundamental_provider import TencentFundamentalProvider
from src.data.providers.history_provider import (
    MIN_BARS_FOR_FULL_TECHNICALS,
    GoldenHistoryProvider,
    MarketHistoryProvider,
)
from src.data.providers.eastmoney_news_provider import EastMoneyAnnouncementProvider
from src.data.providers.quote_provider import GoldenQuoteProvider, QuoteProvider
from src.data.providers.tencent_history_provider import TencentHistoryProvider
from src.data.providers.sina_quote_provider import (
    SINA_QUOTE_PROVIDER_ID,
    SinaQuoteProvider,
)
from src.data.validation.gate import DataTrustGate
from src.quant.technical.indicators import (
    compute_macd,
    compute_momentum_indicator,
    compute_moving_average,
    compute_realized_volatility,
    compute_rsi,
    compute_volume_indicator,
)

NOT_AVAILABLE_TEXT = "暂无数据"

# Data-source modes. REAL is the default: the Terminal is a live-quote product, and demo data is
# something the user opts into, not something they are silently served.
QUOTE_SOURCE_REAL = "REAL"
QUOTE_SOURCE_DEMO = "DEMO"
DEFAULT_QUOTE_SOURCE = QUOTE_SOURCE_REAL

REAL_DATA_STATUS = "REAL DATA"
DEMO_DATA_STATUS = "DEMO DATA"

# Reasons a fundamental row can be empty. Each is specific: "the source does not report it" and
# "the metric is not modelled at all" are different facts, and a user deserves to know which.
_FIELD_NOT_PROVIDED_BY_SOURCE = "当前基本面数据源未提供该指标。"
_FIELD_NOT_MODELLED_ANYWHERE = "该指标尚未纳入当前数据契约，也无可验证的数据源；不做估算。"

# How many daily bars the Terminal asks for. Comfortably above MACD's 34-bar warm-up so several
# valid points exist, without pulling years of history a consumer page never shows.
HISTORY_BAR_LIMIT = 120

INSUFFICIENT_HISTORY_REASON = (
    "该股票可获取的历史交易日不足，无法计算该指标；不会用其他数据补齐。"
)

DISCLAIMER = "本页面仅提供信息与分析，不构成投资建议。"

AI_UNAVAILABLE_NOTICE = (
    "AI 分析暂未开通：尚未配置大模型服务。开通后，这里会显示 AI 总结、主要风险与"
    "看多/看空因素。"
)

DEMO_DATA_NOTICE = (
    "DEMO DATA — 当前显示的是演示数据集，不是实时行情。在左侧「数据源」切换到"
    "「实时行情」即可查看真实数据。"
)


def humanize_volume(shares: float) -> str:
    """成交量, A股惯例以「手」计 (1手 = 100股). Pure formatting — the underlying share count is
    未经改动 and stays available on the view for anyone who wants the raw number."""
    if shares < 0:
        raise ValueError(f"FAIL CLOSED: negative volume {shares}.")
    lots = shares / 100.0
    if lots >= 1e4:
        return f"{lots / 1e4:.2f}万手"
    return f"{lots:,.0f}手"


def humanize_amount(yuan: float) -> str:
    """成交额, in 亿元/万元 as every consumer terminal displays it."""
    if yuan < 0:
        raise ValueError(f"FAIL CLOSED: negative amount {yuan}.")
    if yuan >= 1e8:
        return f"{yuan / 1e8:.2f}亿元"
    if yuan >= 1e4:
        return f"{yuan / 1e4:.2f}万元"
    return f"{yuan:,.0f}元"


def summarize_technicals(readings) -> str:
    """A neutral tally of the panel's readings ("偏强 2 项 · 中性 3 项"), first-seen order.
    Descriptive only — it counts labels that already exist and never produces a verdict,
    recommendation or score of its own."""
    counts: Dict[str, int] = {}
    missing = 0
    for reading in readings:
        if not reading.available:
            missing += 1
            continue
        counts[reading.plain_reading] = counts.get(reading.plain_reading, 0) + 1
    parts = [f"{label} {n} 项" for label, n in counts.items()]
    if missing:
        parts.append(f"{NOT_AVAILABLE_TEXT} {missing} 项")
    return "　·　".join(parts) if parts else f"{NOT_AVAILABLE_TEXT}"


def is_ai_available() -> bool:
    """True only when a real LLM credential is configured. The Terminal shows an honest
    「暂未开通」 notice instead of offering a consumer a placeholder narrative — the
    labelled-synthetic path remains available in Research mode, untouched."""
    return analyst.get_llm_provider_status().status == analyst.LLM_AVAILABLE_STATUS


class TerminalError(Exception):
    """Wraps any failure for UI display. Never swallows and never substitutes a default."""


# --- Views (plain data; no framework types) -----------------------------------------------------

@dataclass(frozen=True)
class QuoteView:
    symbol: str
    display_name: str
    last_price: float
    change: float
    change_pct: float
    open_price: float
    high_price: float
    low_price: float
    prev_close: float
    volume: float
    amount: float
    updated_at: str          # 数据更新时间 — the vendor's timestamp, not our receipt time
    data_source: str         # 数据来源, in plain words
    is_demo: bool
    demo_notice: Optional[str]
    market_session: str
    trading_status: str
    data_status: str = DEMO_DATA_STATUS   # "REAL DATA" | "DEMO DATA", shown verbatim in the UI


@dataclass(frozen=True)
class TechnicalReadingView:
    name: str                # 普通人看得懂的名字, e.g. "MACD"
    plain_reading: str       # e.g. "偏强"
    explanation: str         # e.g. "近期上涨动能仍然存在"
    detail: str              # the actual number, kept visible rather than hidden
    available: bool


@dataclass(frozen=True)
class FundamentalRowView:
    label: str               # 营收 / 净利润 / ...
    value: str               # formatted, or 暂无数据
    available: bool
    reason: Optional[str]    # why it is missing — never a blank


@dataclass(frozen=True)
class NewsItemView:
    title: str
    published_at: str
    source: str
    summary: str
    source_url: Optional[str] = None
    symbol: str = ""


@dataclass(frozen=True)
class NewsPanelView:
    """The news panel declares its OWN source, exactly like the quote, history and fundamental
    panels. Four feeds, four source labels — never one combined claim."""
    items: Tuple[NewsItemView, ...]
    data_source: str
    is_demo: bool
    unavailable_reason: Optional[str] = None


@dataclass(frozen=True)
class AIAnalysisView:
    summary: str
    risk: str
    bull_case: str
    bear_case: str
    narrative_origin: str         # REAL_PROVIDER | SYNTHETIC_DATA
    narrative_warning: Optional[str]
    data_confidence_band: str
    generated_at: str


@dataclass(frozen=True)
class TerminalStockView:
    quote: QuoteView
    price_history: "PriceHistoryView"
    technicals: Tuple[TechnicalReadingView, ...]
    fundamentals: "FundamentalPanelView"
    news: "NewsPanelView"
    disclaimer: str = DISCLAIMER


# --- Symbol search / quote ------------------------------------------------------------------------

def _quote_provider(source: Optional[str] = None) -> QuoteProvider:
    """The single seam between the Terminal and whichever provider serves it. Every panel
    downstream reads provenance off the contract, so nothing else needs to know which provider
    produced a quote.

    There is deliberately NO automatic fallback from REAL to DEMO. If the live source fails, the
    Terminal says so; silently serving demo numbers under a live page is precisely the confusion
    this product must never create.
    """
    mode = source or DEFAULT_QUOTE_SOURCE
    if mode == QUOTE_SOURCE_REAL:
        return SinaQuoteProvider(display_names=dict(SYMBOL_DISPLAY_NAMES))
    if mode == QUOTE_SOURCE_DEMO:
        bars_by_symbol: Dict[str, List[Any]] = {}
        for contract in golden_market_data():
            bars_by_symbol.setdefault(contract.symbol, []).append(contract)
        return GoldenQuoteProvider(bars_by_symbol, display_names=dict(SYMBOL_DISPLAY_NAMES))
    raise TerminalError(
        f"未知的数据源模式 '{mode}'，应为 {QUOTE_SOURCE_REAL} 或 {QUOTE_SOURCE_DEMO}。"
    )


def _fundamental_provider(source: Optional[str] = None) -> FundamentalProvider:
    """The single seam for fundamentals — separate from the quote and history seams on purpose.
    The three feeds have different vendors, different update frequencies and different
    reliability, so each declares its own source rather than being collapsed into one claim."""
    mode = source or DEFAULT_QUOTE_SOURCE
    if mode == QUOTE_SOURCE_REAL:
        return TencentFundamentalProvider()
    if mode == QUOTE_SOURCE_DEMO:
        return GoldenFundamentalProvider(dict(golden_fundamental_data()))
    raise TerminalError(
        f"未知的数据源模式 '{mode}'，应为 {QUOTE_SOURCE_REAL} 或 {QUOTE_SOURCE_DEMO}。"
    )


def _history_provider(source: Optional[str] = None) -> MarketHistoryProvider:
    """The single seam for the daily-bar series, mirroring `_quote_provider`. As with quotes
    there is NO automatic REAL→DEMO fallback: if the live history cannot be fetched, the
    technical panels say 暂无数据 with the reason."""
    mode = source or DEFAULT_QUOTE_SOURCE
    if mode == QUOTE_SOURCE_REAL:
        return TencentHistoryProvider()
    if mode == QUOTE_SOURCE_DEMO:
        bars_by_symbol: Dict[str, List[Any]] = {}
        for contract in golden_market_data():
            bars_by_symbol.setdefault(contract.symbol, []).append(contract)
        return GoldenHistoryProvider(bars_by_symbol)
    raise TerminalError(
        f"未知的数据源模式 '{mode}'，应为 {QUOTE_SOURCE_REAL} 或 {QUOTE_SOURCE_DEMO}。"
    )


def search_stocks(query: str, source: Optional[str] = None) -> List[Dict[str, str]]:
    mode = source or DEFAULT_QUOTE_SOURCE
    try:
        return [
            {"symbol": m["symbol"], "display_name": _display_name(m["display_name"], mode)}
            for m in _quote_provider(mode).search_symbols(query)
        ]
    except ProviderError:
        # A search that cannot reach the live source returns nothing rather than quietly
        # answering from the demo universe.
        return []


# The seeded display names carry a "(GOLDEN_DATASET demo)" suffix. The SYMBOLS themselves are
# real A-share codes; only the label is a demo artefact. Showing that suffix next to a live price
# would misdescribe real data as demo data, so it is stripped in REAL mode.
_DEMO_LABEL_SUFFIX = " (GOLDEN_DATASET demo)"


def _display_name(name: str, mode: str) -> str:
    if mode == QUOTE_SOURCE_REAL and name.endswith(_DEMO_LABEL_SUFFIX):
        return name[: -len(_DEMO_LABEL_SUFFIX)]
    return name


def list_stocks(source: Optional[str] = None) -> List[Dict[str, str]]:
    mode = source or DEFAULT_QUOTE_SOURCE
    return [
        {"symbol": symbol, "display_name": _display_name(name, mode)}
        for symbol, name in sorted(SYMBOL_DISPLAY_NAMES.items())
    ]


# Human-readable names for real sources. A provider absent from this map is still described
# honestly by its id — the label must never assert a vendor that did not serve the quote.
_REAL_SOURCE_NAMES = {SINA_QUOTE_PROVIDER_ID: "新浪财经"}


def _describe_source(quote: QuoteContract) -> str:
    if quote.data_origin == "REAL_PROVIDER":
        vendor = _REAL_SOURCE_NAMES.get(quote.provider_id)
        return (f"实时行情源：{vendor} ({quote.provider_id})" if vendor
                else f"实时行情源 ({quote.provider_id})")
    if quote.data_origin == "GOLDEN_DATASET":
        return "演示数据集 (DEMO DATA)"
    return f"{quote.data_origin} ({quote.provider_id})"


def get_quote_view(symbol: str, source: Optional[str] = None) -> QuoteView:
    try:
        quote = _quote_provider(source).get_quote(symbol)
    except ProviderError as e:
        raise TerminalError(str(e)) from e

    is_valid, errors = DataTrustGate.validate_quote(quote)
    if not is_valid:
        # An internally contradictory quote is not shown to a user as fact, whoever sent it.
        raise TerminalError(f"行情数据未通过校验，不予显示：{errors}")

    return QuoteView(
        symbol=quote.symbol, display_name=quote.display_name, last_price=quote.last_price,
        change=quote.change, change_pct=quote.change_pct, open_price=quote.open_price,
        high_price=quote.high_price, low_price=quote.low_price, prev_close=quote.prev_close,
        volume=quote.volume, amount=quote.amount,
        updated_at=quote.quoted_at.strftime("%Y-%m-%d %H:%M:%S"),
        data_source=_describe_source(quote), is_demo=quote.is_demo,
        demo_notice=DEMO_DATA_NOTICE if quote.is_demo else None,
        market_session=quote.market_session, trading_status=quote.trading_status,
        data_status=DEMO_DATA_STATUS if quote.is_demo else REAL_DATA_STATUS,
    )


# --- Technical readings: deterministic plain language ------------------------------------------------

# (threshold, plain_reading, explanation) evaluated in order; the first match wins. Deliberately
# descriptive, never prescriptive — no rule here produces 买入/卖出 or a target price.
_TECHNICAL_RULES: Dict[str, Tuple[Tuple[float, str, str], ...]] = {
    "RSI": (
        (70.0, "偏高", "短期买盘较强，指标已进入较高区域，历史上此区域后续波动较大。"),
        (30.0, "中性", "买卖力量大致平衡，没有明显的超买或超卖迹象。"),
        (float("-inf"), "偏低", "短期卖压较重，指标处于较低区域。"),
    ),
}


def _rsi_reading(value: float) -> Tuple[str, str]:
    for threshold, reading, explanation in _TECHNICAL_RULES["RSI"]:
        if value >= threshold:
            return reading, explanation
    return "中性", "买卖力量大致平衡。"


def _latest_valid(records: List[Any]) -> Optional[Any]:
    """The most recent record that actually has a value. A warm-up record is a real answer
    ("not enough history yet"), not a value to display."""
    for record in reversed(records):
        if record.warm_up_satisfied and record.calculated_value is not None:
            return record
    return None


def _unavailable(name: str, reason: str) -> TechnicalReadingView:
    return TechnicalReadingView(
        name=name, plain_reading=NOT_AVAILABLE_TEXT, explanation=reason, detail="",
        available=False,
    )


_TECHNICAL_PANEL_NAMES = (
    "趋势 (20日均线)", "RSI (相对强弱)", "MACD (动能)", "成交量", "波动率", "动量 (20日涨跌)",
)


@dataclass(frozen=True)
class PriceHistoryView:
    """The K-line history behind the indicators, in the plainest possible shape for charting."""
    dates: Tuple[str, ...]
    closes: Tuple[float, ...]
    bar_count: int
    data_source: str
    is_demo: bool
    unavailable_reason: Optional[str] = None


def _validated_bars(symbol: str, source: Optional[str] = None):
    """Fetches the daily series and puts EVERY bar through DataTrustGate before it can reach an
    indicator. A bar that fails validation is dropped and counted — never silently repaired, and
    never replaced from another source.

    Returns (bars, provider, rejected_count) or raises TerminalError.
    """
    provider = _history_provider(source)
    try:
        raw_bars = provider.get_daily_bars(symbol, limit=HISTORY_BAR_LIMIT)
    except ProviderError as e:
        raise TerminalError(str(e)) from e

    bars, rejected = [], 0
    for bar in raw_bars:
        is_valid, _errors = DataTrustGate.validate_market_data(bar)
        if is_valid:
            bars.append(bar)
        else:
            rejected += 1
    return bars, provider, rejected


def get_price_history(symbol: str, source: Optional[str] = None) -> PriceHistoryView:
    mode = source or DEFAULT_QUOTE_SOURCE
    is_demo = mode != QUOTE_SOURCE_REAL
    try:
        bars, provider, _rejected = _validated_bars(symbol, mode)
    except TerminalError as e:
        return PriceHistoryView(
            dates=(), closes=(), bar_count=0,
            data_source=DEMO_DATA_STATUS if is_demo else REAL_DATA_STATUS,
            is_demo=is_demo, unavailable_reason=str(e),
        )
    label = ("演示数据集 (DEMO DATA)" if is_demo
             else f"实时历史行情源 ({provider.provider_id})")
    return PriceHistoryView(
        dates=tuple(b.trading_date for b in bars),
        closes=tuple(b.close_price for b in bars),
        bar_count=len(bars), data_source=label, is_demo=is_demo,
    )


def get_technical_views(symbol: str, source: Optional[str] = None
                        ) -> List[TechnicalReadingView]:
    """All readings are computed locally by the SHIPPED indicator functions from a validated
    daily-bar series — never taken from a third party's own reported indicator value.

    REAL and DEMO run the IDENTICAL computation path and differ only in which provider supplies
    the bars, so a reading can never be silently produced from the wrong source. If the series is
    unavailable or too short, every row reports 暂无数据 with the reason; nothing is padded.
    """
    mode = source or DEFAULT_QUOTE_SOURCE
    try:
        bars, provider, _rejected = _validated_bars(symbol, mode)
    except TerminalError as e:
        return [_unavailable(name, str(e)) for name in _TECHNICAL_PANEL_NAMES]

    if not bars:
        return [_unavailable(name, INSUFFICIENT_HISTORY_REASON)
                for name in _TECHNICAL_PANEL_NAMES]

    # Availability is decided PER INDICATOR, not by one blanket threshold: each has its own
    # warm-up (MACD needs 34 bars, MA20 needs 20, RSI14 needs 15). A single gate at MACD's
    # requirement would hide five perfectly computable readings whenever the series is short.
    short_history = (
        f"{INSUFFICIENT_HISTORY_REASON}（仅 {len(bars)} 个交易日，"
        f"该指标需要更长的历史）"
    )

    dates = [b.trading_date for b in bars]
    prices = [b.close_price for b in bars]
    volumes = [b.volume for b in bars]
    # The price basis is taken from the PROVIDER, never assumed by this layer — mislabelling it
    # would attach a false adjustment claim to every indicator computed here.
    basis = dict(input_price_basis=provider.input_price_basis,
                 data_origin=bars[-1].data_origin)

    views: List[TechnicalReadingView] = []

    ma = _latest_valid(compute_moving_average(symbol, dates, prices, window=20, **basis))
    if ma is None:
        views.append(_unavailable("趋势 (20日均线)", short_history))
    else:
        above = prices[-1] >= ma.calculated_value
        views.append(TechnicalReadingView(
            name="趋势 (20日均线)",
            plain_reading="偏强" if above else "偏弱",
            explanation=("最新价高于20日均线，中期趋势向上。" if above
                         else "最新价低于20日均线，中期趋势偏弱。"),
            detail=f"最新收盘 {prices[-1]:.2f}，20日均线 {ma.calculated_value:.2f}",
            available=True,
        ))

    rsi = _latest_valid(compute_rsi(symbol, dates, prices, window=14, **basis))
    if rsi is None:
        views.append(_unavailable("RSI (相对强弱)", short_history))
    else:
        reading, explanation = _rsi_reading(rsi.calculated_value)
        views.append(TechnicalReadingView(
            name="RSI (相对强弱)", plain_reading=reading, explanation=explanation,
            detail=f"RSI(14) = {rsi.calculated_value:.2f}", available=True,
        ))

    macd = _latest_valid(compute_macd(symbol, dates, prices, **basis))
    if macd is None:
        views.append(_unavailable("MACD (动能)", short_history))
    else:
        histogram = macd.calculated_value["histogram"]
        strong = histogram >= 0
        views.append(TechnicalReadingView(
            name="MACD (动能)",
            plain_reading="偏强" if strong else "偏弱",
            explanation=("快线仍在慢线之上，近期上涨动能仍然存在。" if strong
                         else "快线已跌破慢线，上涨动能正在减弱。"),
            detail=(f"MACD {macd.calculated_value['macd_line']:.4f}，"
                    f"信号线 {macd.calculated_value['signal_line']:.4f}"),
            available=True,
        ))

    volume = _latest_valid(compute_volume_indicator(
        symbol, dates, volumes, window=20, data_origin=bars[-1].data_origin))
    if volume is None:
        views.append(_unavailable("成交量", short_history))
    else:
        ratio = volume.calculated_value["volume_ratio"]
        if ratio is None:
            views.append(_unavailable("成交量", "该期间成交量为零，无法与均量比较。"))
        else:
            if ratio >= 1.5:
                reading, explanation = "放量", "成交量明显高于近期平均，市场关注度上升。"
            elif ratio <= 0.7:
                reading, explanation = "缩量", "成交量低于近期平均，交投相对清淡。"
            else:
                reading, explanation = "平稳", "成交量与近期平均相当，没有明显异动。"
            views.append(TechnicalReadingView(
                name="成交量", plain_reading=reading, explanation=explanation,
                detail=f"最新成交量为20日均量的 {ratio:.2f} 倍", available=True,
            ))

    vol = _latest_valid(compute_realized_volatility(symbol, dates, prices, window=20, **basis))
    if vol is None:
        views.append(_unavailable("波动率", short_history))
    else:
        annualized = vol.calculated_value
        if annualized >= 0.40:
            reading, explanation = "偏高", "近期价格波动较大，短线风险相对较高。"
        elif annualized <= 0.15:
            reading, explanation = "偏低", "近期价格波动较小，走势相对平稳。"
        else:
            reading, explanation = "中等", "近期波动处于常见区间。"
        views.append(TechnicalReadingView(
            name="波动率", plain_reading=reading, explanation=explanation,
            detail=f"年化波动率 {annualized * 100:.1f}%", available=True,
        ))

    momentum = _latest_valid(compute_momentum_indicator(symbol, dates, prices, window=20, **basis))
    if momentum is None:
        views.append(_unavailable("动量 (20日涨跌)", short_history))
    else:
        change_pct = momentum.calculated_value * 100
        if change_pct > 0:
            reading, explanation = "上涨", f"过去20个交易日累计上涨 {change_pct:.1f}%。"
        elif change_pct < 0:
            reading, explanation = "下跌", f"过去20个交易日累计下跌 {abs(change_pct):.1f}%。"
        else:
            reading, explanation = "持平", "过去20个交易日基本持平。"
        views.append(TechnicalReadingView(
            name="动量 (20日涨跌)", plain_reading=reading, explanation=explanation,
            detail=f"20日涨跌幅 {change_pct:+.2f}%", available=True,
        ))

    return views


# --- Fundamentals -------------------------------------------------------------------------------

# (label, contract attribute, formatter), in the order the CEO directive lists them.
# `None` as the attribute means the metric is not modelled by FundamentalDataContract AND no
# verifiable free source reports it — surfaced honestly rather than dropped from the table.
_FUNDAMENTAL_ROWS: Tuple[Tuple[str, Optional[str], str], ...] = (
    ("总市值", "market_cap", "money"),
    ("市盈率 (PE)", "pe_ttm", "number"),
    ("市净率 (PB)", "pb", "number"),
    ("净资产收益率 (ROE)", "roe", "percent"),
    ("营收", "revenue", "money"),
    ("净利润", "net_income", "money"),
    ("毛利率", None, "percent"),
    ("净利率", None, "percent"),
    ("每股收益 (EPS)", "eps_ttm", "number"),
)


@dataclass(frozen=True)
class FundamentalPanelView:
    """The fundamental panel carries its OWN source and date. Quotes, K-line history and
    fundamentals come from different feeds, and telling a user that fundamentals arrived with the
    price would be false."""
    rows: Tuple[FundamentalRowView, ...]
    data_date: str
    data_source: str
    is_demo: bool
    unavailable_reason: Optional[str] = None


def _format_value(value: float, kind: str) -> str:
    if kind == "money":
        if abs(value) >= 1e8:
            return f"{value / 1e8:.2f} 亿元"
        if abs(value) >= 1e4:
            return f"{value / 1e4:.2f} 万元"
        return f"{value:.2f} 元"
    if kind == "percent":
        return f"{value:.2f}%"
    return f"{value:.2f}"


def _rows_from_contract(contract) -> List[FundamentalRowView]:
    rows: List[FundamentalRowView] = []
    for label, attribute, kind in _FUNDAMENTAL_ROWS:
        if attribute is None:
            rows.append(FundamentalRowView(
                label, NOT_AVAILABLE_TEXT, False, _FIELD_NOT_MODELLED_ANYWHERE))
            continue
        value = getattr(contract, attribute, None) if contract is not None else None
        if value is None:
            rows.append(FundamentalRowView(
                label, NOT_AVAILABLE_TEXT, False, _FIELD_NOT_PROVIDED_BY_SOURCE))
            continue
        rows.append(FundamentalRowView(label, _format_value(value, kind), True, None))
    return rows


def _all_unavailable(reason: str) -> List[FundamentalRowView]:
    return [FundamentalRowView(label, NOT_AVAILABLE_TEXT, False, reason)
            for label, _, _ in _FUNDAMENTAL_ROWS]


def get_fundamentals_panel(symbol: str, source: Optional[str] = None) -> FundamentalPanelView:
    """Every row is always present. A missing number renders as 暂无数据 WITH A REASON — never
    omitted from the table, never estimated, and never back-filled from the other mode."""
    mode = source or DEFAULT_QUOTE_SOURCE
    is_demo = mode != QUOTE_SOURCE_REAL
    try:
        provider = _fundamental_provider(mode)
        contract = provider.get_fundamentals(symbol)
    except (TerminalError, ProviderError) as e:
        return FundamentalPanelView(
            rows=tuple(_all_unavailable(str(e))), data_date=NOT_AVAILABLE_TEXT,
            data_source=DEMO_DATA_STATUS if is_demo else REAL_DATA_STATUS,
            is_demo=is_demo, unavailable_reason=str(e),
        )

    is_valid, errors = DataTrustGate.validate_fundamental_data(contract)
    if not is_valid:
        reason = f"基本面数据未通过校验，不予显示：{errors}"
        return FundamentalPanelView(
            rows=tuple(_all_unavailable(reason)), data_date=NOT_AVAILABLE_TEXT,
            data_source=provider.source_label, is_demo=is_demo, unavailable_reason=reason,
        )

    # The accounting period, when the source discloses one; otherwise the valuation date, with
    # the absence of a report period stated rather than papered over.
    if contract.report_date and contract.report_date != REPORT_PERIOD_NOT_DISCLOSED:
        data_date = f"报告期 {contract.report_date}"
    else:
        data_date = f"估值日期 {contract.trade_date}（数据源未披露对应报告期）"

    return FundamentalPanelView(
        rows=tuple(_rows_from_contract(contract)), data_date=data_date,
        data_source=provider.source_label, is_demo=is_demo,
    )


def get_fundamental_views(symbol: str, source: Optional[str] = None
                          ) -> List[FundamentalRowView]:
    """Row-only view, retained for callers that do not need the panel's source metadata."""
    return list(get_fundamentals_panel(symbol, source).rows)


# --- News ---------------------------------------------------------------------------------------

# How far back the Terminal looks for announcements. Long enough that a quiet company still shows
# something, short enough that "最新消息" stays a fair description.
NEWS_LOOKBACK_DAYS = 180
NEWS_DISPLAY_LIMIT = 15

DEMO_NEWS_UNAVAILABLE_REASON = (
    "演示数据集不包含新闻/公告，且不会用合成新闻填充。切换到「实时行情」可查看真实公告。"
)


def _news_provider(source: Optional[str] = None):
    """The fourth seam. REAL mode reaches a live announcement source; DEMO mode has none, and
    says so rather than serving synthetic headlines."""
    mode = source or DEFAULT_QUOTE_SOURCE
    if mode == QUOTE_SOURCE_REAL:
        return EastMoneyAnnouncementProvider()
    if mode == QUOTE_SOURCE_DEMO:
        return None
    raise TerminalError(
        f"未知的数据源模式 '{mode}'，应为 {QUOTE_SOURCE_REAL} 或 {QUOTE_SOURCE_DEMO}。"
    )


def get_news_panel(symbol: str, source: Optional[str] = None) -> NewsPanelView:
    """Real company announcements, each validated before it may be displayed.

    A fabricated news item is the single most misleading thing this product could show, so there
    is no synthetic fallback anywhere on this path: DEMO mode reports that it has no news source,
    and a REAL-mode failure reports the failure — neither ever substitutes the other.
    """
    mode = source or DEFAULT_QUOTE_SOURCE
    is_demo = mode != QUOTE_SOURCE_REAL

    provider = _news_provider(mode)
    if provider is None:
        return NewsPanelView(
            items=(), data_source="演示数据集 (DEMO DATA)", is_demo=True,
            unavailable_reason=DEMO_NEWS_UNAVAILABLE_REASON,
        )

    end = datetime.now()
    start = end - timedelta(days=NEWS_LOOKBACK_DAYS)
    try:
        page = provider.fetch_news_announcements(
            symbol, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        )
    except ProviderError as e:
        return NewsPanelView(
            items=(), data_source=provider.source_label, is_demo=False,
            unavailable_reason=str(e),
        )

    items: List[NewsItemView] = []
    for contract in page.items:
        # Validation stage: an item that fails the gate is excluded, never repaired and never
        # shown with a caveat.
        is_valid, _errors = DataTrustGate.validate_news_announcement(contract)
        if not is_valid:
            continue
        items.append(NewsItemView(
            title=contract.title,
            published_at=contract.published_at.strftime("%Y-%m-%d"),
            source=contract.source,
            summary=contract.body_summary,   # empty by design — never paraphrased or generated
            source_url=contract.source_url,
            symbol=contract.symbols[0] if contract.symbols else "",
        ))

    items.sort(key=lambda i: i.published_at, reverse=True)
    reason = None if items else "该股票在最近半年内没有可获取的公告。"
    return NewsPanelView(
        items=tuple(items[:NEWS_DISPLAY_LIMIT]), data_source=provider.source_label,
        is_demo=False, unavailable_reason=reason,
    )


def get_news_views(symbol: str, source: Optional[str] = None
                   ) -> Tuple[List[NewsItemView], Optional[str]]:
    """Item-only view, retained for callers that do not need the panel's source metadata."""
    panel = get_news_panel(symbol, source)
    return list(panel.items), panel.unavailable_reason


# --- Assembled page -------------------------------------------------------------------------------

def get_stock_view(symbol: str, source: Optional[str] = None) -> TerminalStockView:
    """Assembles one page from ONE data source. A page never blends REAL and DEMO: panels with
    no source in the active mode report 暂无数据 with the reason."""
    mode = source or DEFAULT_QUOTE_SOURCE
    return TerminalStockView(
        quote=get_quote_view(symbol, mode),
        price_history=get_price_history(symbol, mode),
        technicals=tuple(get_technical_views(symbol, mode)),
        fundamentals=get_fundamentals_panel(symbol, mode),
        news=get_news_panel(symbol, mode),
    )


# --- AI analysis ----------------------------------------------------------------------------------

def get_ai_analysis(
    symbol: str, as_of: Optional[Any] = None, allow_synthetic_narrative: bool = True,
) -> AIAnalysisView:
    """Reuses the Research-mode analyst pipeline unchanged: Evidence → validation → LLM →
    citation validator → report. Terminal mode only re-presents four of its sections in plain
    language; it does not add a second, laxer AI path.

    Raises TerminalError (never returns a placeholder) if the report cannot be produced.
    """
    if as_of is None:
        bars = [c.trading_date for c in golden_market_data() if c.symbol == symbol]
        if not bars:
            raise TerminalError(f"没有可用于 '{symbol}' 的行情序列。")
        as_of = max(bars)

    try:
        report = analyst.generate_analyst_report(
            symbol, as_of, allow_synthetic_narrative=allow_synthetic_narrative,
        )
    except analyst.ResearchAnalystError as e:
        raise TerminalError(str(e)) from e

    sections = {section.number: section for section in report.sections}
    return AIAnalysisView(
        summary=sections[1].body,
        risk=sections[8].body,
        bull_case=sections[6].body,
        bear_case=sections[7].body,
        narrative_origin=report.narrative_origin,
        narrative_warning=report.narrative_warning,
        data_confidence_band=report.data_confidence.band,
        generated_at=report.generated_at,
    )
