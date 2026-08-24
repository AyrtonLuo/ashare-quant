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
from datetime import date, datetime
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
from src.data.providers.quote_provider import GoldenQuoteProvider, QuoteProvider
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

# Real quotes are live; the historical bar series behind the indicators is NOT yet wired to a
# real source (that is a separate data feed from the quote endpoint). Rather than compute
# indicators from demo history and display them beside a real price -- which would mix REAL and
# DEMO on one page -- those panels report 暂无数据 with this reason.
REAL_MODE_NO_HISTORY_REASON = (
    "实时模式下尚未接入真实历史行情序列，因此不展示由历史数据计算的指标；"
    "不会用演示数据代替真实数据。"
)
REAL_MODE_NO_FUNDAMENTAL_REASON = (
    "实时模式下尚未接入真实财务数据源；不会用演示数据代替真实数据。"
)

DISCLAIMER = "本页面仅提供信息与分析，不构成投资建议。"

DEMO_DATA_NOTICE = (
    "DEMO DATA — 当前显示的是演示数据集，不是实时行情。真实行情数据源尚未接入；"
    "接入后本页会自动显示真实来源与更新时间。"
)


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
    technicals: Tuple[TechnicalReadingView, ...]
    fundamentals: Tuple[FundamentalRowView, ...]
    news: Tuple[NewsItemView, ...]
    news_unavailable_reason: Optional[str]
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


def get_technical_views(symbol: str, source: Optional[str] = None
                        ) -> List[TechnicalReadingView]:
    """All readings are computed locally by the SHIPPED indicator functions — never taken from a
    third party's own reported indicator value.

    In REAL mode they are reported as 暂无数据: the live quote endpoint serves a quote, not a
    historical bar series, and computing indicators from demo history to sit beside a real price
    would put REAL and DEMO data on the same page.
    """
    if (source or DEFAULT_QUOTE_SOURCE) == QUOTE_SOURCE_REAL:
        return [_unavailable(name, REAL_MODE_NO_HISTORY_REASON)
                for name in _TECHNICAL_PANEL_NAMES]

    bars = sorted(
        [c for c in golden_market_data() if c.symbol == symbol],
        key=lambda c: c.trading_date,
    )
    if not bars:
        raise TerminalError(f"没有可用于 '{symbol}' 的行情序列。")

    dates = [b.trading_date for b in bars]
    prices = [b.close_price for b in bars]
    volumes = [b.volume for b in bars]
    basis = dict(input_price_basis="RAW", data_origin=GOLDEN_DATA_ORIGIN)
    short_history = "历史数据不足，指标尚未满足计算所需的最小周期。"

    views: List[TechnicalReadingView] = []

    # --- 趋势 (MA)
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
            detail=f"最新价 {prices[-1]:.2f}，20日均线 {ma.calculated_value:.2f}",
            available=True,
        ))

    # --- RSI
    rsi = _latest_valid(compute_rsi(symbol, dates, prices, window=14, **basis))
    if rsi is None:
        views.append(_unavailable("RSI (相对强弱)", short_history))
    else:
        reading, explanation = _rsi_reading(rsi.calculated_value)
        views.append(TechnicalReadingView(
            name="RSI (相对强弱)", plain_reading=reading, explanation=explanation,
            detail=f"RSI(14) = {rsi.calculated_value:.2f}", available=True,
        ))

    # --- MACD
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

    # --- 成交量
    volume = _latest_valid(compute_volume_indicator(symbol, dates, volumes, window=20,
                                                    data_origin=GOLDEN_DATA_ORIGIN))
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

    # --- 波动率
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

    # --- 动量
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


# --- Fundamentals ---------------------------------------------------------------------------------

# (label, contract attribute, formatter). `None` as the attribute means the field is not modelled
# by FundamentalDataContract at all — reported honestly rather than silently omitted from the list.
_FUNDAMENTAL_ROWS: Tuple[Tuple[str, Optional[str], str], ...] = (
    ("营收", "revenue", "money"),
    ("净利润", "net_income", "money"),
    ("每股收益 (EPS)", "eps_ttm", "number"),
    ("净资产收益率 (ROE)", "roe", "percent"),
    ("毛利率", None, "percent"),
    ("经营现金流", "operating_cash_flow", "money"),
    ("市盈率 (PE)", "pe_ttm", "number"),
    ("市净率 (PB)", "pb", "number"),
)

_FIELD_NOT_MODELLED = "该指标尚未纳入当前数据契约，不做估算。"
_FIELD_NOT_PROVIDED = "当前数据源未提供该指标。"


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


def get_fundamental_views(symbol: str, source: Optional[str] = None
                          ) -> List[FundamentalRowView]:
    """Every row is always present in the output. A missing number renders as 暂无数据 with a
    reason — never omitted from the table, and never estimated.

    In REAL mode every row is 暂无数据: no real fundamental source is wired, and showing demo
    fundamentals beside a real price would mix the two."""
    if (source or DEFAULT_QUOTE_SOURCE) == QUOTE_SOURCE_REAL:
        return [
            FundamentalRowView(label, NOT_AVAILABLE_TEXT, False, REAL_MODE_NO_FUNDAMENTAL_REASON)
            for label, _, _ in _FUNDAMENTAL_ROWS
        ]

    records = golden_fundamental_data().get(symbol, [])
    latest = records[-1] if records else None

    rows: List[FundamentalRowView] = []
    for label, attribute, kind in _FUNDAMENTAL_ROWS:
        if attribute is None:
            rows.append(FundamentalRowView(label, NOT_AVAILABLE_TEXT, False, _FIELD_NOT_MODELLED))
            continue
        value = getattr(latest, attribute, None) if latest is not None else None
        if value is None:
            rows.append(FundamentalRowView(label, NOT_AVAILABLE_TEXT, False, _FIELD_NOT_PROVIDED))
            continue
        rows.append(FundamentalRowView(label, _format_value(value, kind), True, None))
    return rows


# --- News -----------------------------------------------------------------------------------------

NEWS_UNAVAILABLE_REASON = (
    "尚未接入新闻/公告数据源。此处不显示任何内容，也不会用其他数据推测新闻。"
)


def get_news_views(symbol: str) -> Tuple[List[NewsItemView], Optional[str]]:
    """No news vendor is wired (`LiveNewsAnnouncementProvider` refuses by design), so this
    returns an empty list plus the reason. It never falls back to a synthetic headline: a
    fabricated news item is the single most misleading thing this product could show."""
    return [], NEWS_UNAVAILABLE_REASON


# --- Assembled page -------------------------------------------------------------------------------

def get_stock_view(symbol: str, source: Optional[str] = None) -> TerminalStockView:
    """Assembles one page from ONE data source. A page never blends REAL and DEMO: panels with
    no source in the active mode report 暂无数据 with the reason."""
    mode = source or DEFAULT_QUOTE_SOURCE
    news, news_reason = get_news_views(symbol)
    return TerminalStockView(
        quote=get_quote_view(symbol, mode),
        technicals=tuple(get_technical_views(symbol, mode)),
        fundamentals=tuple(get_fundamental_views(symbol, mode)),
        news=tuple(news),
        news_unavailable_reason=news_reason,
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
