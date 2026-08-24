"""
test_terminal_application_t2.py — Terminal mode Application Layer + UI boundary
(Terminal directive step T2).

The Terminal's product promise is that a non-expert can read it, and its safety promise is that
nothing on it is invented. These tests assert the second one structurally: demo data announces
itself, missing data says 暂无数据 with a reason, no news is fabricated, and the plain-language
technical readings are produced by deterministic code rather than by a model.
"""

import ast
import os
import re

import pytest

from src.app import research_analyst_application as analyst
from src.app import terminal_application as terminal

SYMBOL = "600519.SH"

# These tests cover the DEMO data path. Since T3 made REAL the default source, the mode is now
# stated explicitly rather than relying on a default that has since changed.
DEMO = "DEMO"
APP_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "app")
UI_FILE = os.path.join(APP_DIR, "streamlit_app.py")
TERMINAL_APP_FILE = os.path.join(APP_DIR, "terminal_application.py")


@pytest.fixture(autouse=True)
def _isolated_report_store(tmp_path):
    analyst.reset_report_store(base_dir=str(tmp_path / "analyst_reports"))
    yield
    analyst.reset_report_store()


def _source(path):
    with open(path, "r") as f:
        return f.read()


# --- Search / selection -----------------------------------------------------------------------

def test_search_finds_a_stock_by_code_and_by_chinese_name():
    assert terminal.search_stocks("600519")[0]["symbol"] == SYMBOL
    assert terminal.search_stocks("茅台")[0]["symbol"] == SYMBOL


def test_search_with_no_match_returns_empty_rather_than_guessing():
    assert terminal.search_stocks("NOT_A_REAL_NAME") == []


def test_list_stocks_returns_the_demo_universe():
    stocks = terminal.list_stocks()
    assert {s["symbol"] for s in stocks} >= {SYMBOL}
    assert all(s["display_name"] for s in stocks)


# --- Quote panel ------------------------------------------------------------------------------

def test_quote_view_exposes_every_field_the_directive_requires():
    quote = terminal.get_quote_view(SYMBOL, DEMO)
    assert quote.display_name and quote.symbol == SYMBOL
    assert quote.last_price > 0
    assert isinstance(quote.change_pct, float)
    assert quote.volume >= 0 and quote.amount >= 0
    assert quote.updated_at          # 数据更新时间
    assert quote.data_source         # 数据来源


def test_demo_quote_is_labelled_as_demo_not_as_live():
    quote = terminal.get_quote_view(SYMBOL, DEMO)
    assert quote.is_demo is True
    assert "DEMO DATA" in quote.demo_notice
    assert "不是实时行情" in quote.demo_notice
    assert "演示数据集" in quote.data_source


def test_the_demo_badge_is_driven_by_provenance_not_by_a_ui_flag():
    """A UI author cannot forget the badge: it comes off the contract's own data_origin."""
    from datetime import datetime
    from src.data.contracts.quote import QuoteContract

    real = QuoteContract(
        symbol=SYMBOL, display_name="x", last_price=10.0, prev_close=10.0, open_price=10.0,
        high_price=10.0, low_price=10.0, volume=1.0, amount=10.0,
        quoted_at=datetime(2026, 1, 1), received_at=datetime(2026, 1, 1),
        market_session="OPEN", trading_status="NORMAL", provider_id="p",
        data_origin="REAL_PROVIDER",
    )
    assert terminal._describe_source(real) == "实时行情源 (p)"   # unknown provider named by id
    assert real.is_demo is False


def test_change_pct_matches_the_prices_displayed_beside_it():
    quote = terminal.get_quote_view(SYMBOL, DEMO)
    expected = (quote.last_price - quote.prev_close) / quote.prev_close * 100
    assert quote.change_pct == pytest.approx(expected, abs=1e-6)


def test_unknown_symbol_fails_closed_rather_than_showing_an_empty_card():
    with pytest.raises(terminal.TerminalError):
        terminal.get_quote_view("999999.XX", DEMO)


# --- Technical panel: deterministic plain language ------------------------------------------------

def test_technical_readings_are_in_plain_language_with_the_number_kept_visible():
    readings = {r.name: r for r in terminal.get_technical_views(SYMBOL, DEMO)}
    assert "趋势 (20日均线)" in readings
    assert "RSI (相对强弱)" in readings
    assert "MACD (动能)" in readings
    assert "成交量" in readings

    trend = readings["趋势 (20日均线)"]
    assert trend.plain_reading in ("偏强", "偏弱")
    assert trend.explanation                 # 人话解释
    assert trend.detail                      # 数字并未被隐藏


def test_every_expected_indicator_appears_even_when_it_cannot_be_computed():
    """MACD needs more history than the demo set has. It must still appear, saying 暂无数据 —
    silently dropping the row would hide the gap."""
    readings = {r.name: r for r in terminal.get_technical_views(SYMBOL, DEMO)}
    macd = readings["MACD (动能)"]
    if not macd.available:
        assert macd.plain_reading == terminal.NOT_AVAILABLE_TEXT
        # Wording tightened in T3.5 to name the actual bar count and to state that nothing is
        # substituted; the guarantee under test is unchanged.
        assert "历史交易日不足" in macd.explanation
        assert "不会用其他数据补齐" in macd.explanation


def test_technical_readings_are_deterministic():
    first = terminal.get_technical_views(SYMBOL, DEMO)
    second = terminal.get_technical_views(SYMBOL, DEMO)
    assert [(r.name, r.plain_reading, r.detail) for r in first] == \
           [(r.name, r.plain_reading, r.detail) for r in second]


def test_technical_readings_contain_no_buy_or_sell_advice():
    for reading in terminal.get_technical_views(SYMBOL, DEMO):
        text = reading.plain_reading + reading.explanation + reading.detail
        for forbidden in ("买入", "卖出", "建议买", "建议卖", "目标价", "满仓", "清仓"):
            assert forbidden not in text


def test_the_plain_language_layer_never_calls_an_llm():
    """The readings are code, not a model — asserted against the module's imports."""
    tree = ast.parse(_source(TERMINAL_APP_FILE))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(m.startswith("src.llm") for m in imported)


@pytest.mark.parametrize("value,expected", [
    (85.0, "偏高"), (50.0, "中性"), (10.0, "偏低"),
])
def test_rsi_thresholds_map_to_the_documented_readings(value, expected):
    assert terminal._rsi_reading(value)[0] == expected


# --- Fundamentals: 暂无数据 with a reason, never estimated -----------------------------------------

def test_every_fundamental_row_the_directive_lists_is_present():
    """The row set follows the T4 directive's own priority list, which replaced 经营现金流 with
    总市值 and 净利率."""
    labels = [row.label for row in terminal.get_fundamental_views(SYMBOL, DEMO)]
    for required in ("总市值", "市盈率 (PE)", "市净率 (PB)", "净资产收益率 (ROE)", "营收",
                     "净利润", "毛利率", "净利率", "每股收益 (EPS)"):
        assert required in labels


def test_missing_fundamentals_say_暂无数据_and_explain_why():
    rows = {row.label: row for row in terminal.get_fundamental_views(SYMBOL, DEMO)}
    revenue = rows["营收"]
    assert revenue.available is False
    assert revenue.value == terminal.NOT_AVAILABLE_TEXT
    assert revenue.reason                       # never a blank reason


def test_a_field_not_modelled_at_all_is_reported_honestly():
    """毛利率 is not a field on FundamentalDataContract. It is reported as absent for that
    reason, rather than being quietly dropped from the table or derived from other numbers."""
    rows = {row.label: row for row in terminal.get_fundamental_views(SYMBOL, DEMO)}
    margin = rows["毛利率"]
    assert margin.available is False
    assert "尚未纳入当前数据契约" in margin.reason
    assert "不做估算" in margin.reason


def test_an_available_fundamental_shows_its_real_value():
    rows = {row.label: row for row in terminal.get_fundamental_views(SYMBOL, DEMO)}
    pe = rows["市盈率 (PE)"]
    assert pe.available is True
    assert pe.value != terminal.NOT_AVAILABLE_TEXT
    assert re.match(r"^\d+\.\d{2}$", pe.value)


def test_no_fundamental_value_is_ever_zero_filled():
    for row in terminal.get_fundamental_views(SYMBOL, DEMO):
        if not row.available:
            assert row.value == terminal.NOT_AVAILABLE_TEXT
            assert row.value != "0.00"


# --- News: never fabricated ---------------------------------------------------------------------------

def test_news_is_empty_and_says_why_rather_than_inventing_headlines():
    news, reason = terminal.get_news_views(SYMBOL)
    assert news == []
    assert "尚未接入新闻" in reason
    assert "不会用其他数据推测新闻" in reason


def test_the_assembled_page_carries_the_news_reason():
    view = terminal.get_stock_view(SYMBOL, DEMO)
    assert view.news == ()
    assert view.news_unavailable_reason


# --- Assembled page + disclaimer -------------------------------------------------------------------------

def test_stock_view_assembles_every_panel():
    view = terminal.get_stock_view(SYMBOL, DEMO)
    assert view.quote.symbol == SYMBOL
    assert len(view.technicals) >= 4
    # T4 turned the fundamentals into a panel carrying its own source and date.
    assert len(view.fundamentals.rows) == 9
    assert view.fundamentals.data_source and view.fundamentals.data_date
    assert view.disclaimer == terminal.DISCLAIMER


def test_the_disclaimer_is_the_wording_the_ceo_approved():
    assert terminal.DISCLAIMER == "本页面仅提供信息与分析，不构成投资建议。"


# --- AI analysis reuses the certified pipeline ---------------------------------------------------------------

def test_ai_analysis_returns_summary_risk_bull_and_bear(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    analysis = terminal.get_ai_analysis(SYMBOL)
    assert analysis.summary and analysis.risk
    assert analysis.bull_case and analysis.bear_case
    assert analysis.bull_case != analysis.bear_case
    assert analysis.data_confidence_band in ("HIGH", "MEDIUM", "LOW")


def test_ai_analysis_labels_a_synthetic_narrative(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    analysis = terminal.get_ai_analysis(SYMBOL)
    assert analysis.narrative_origin == "SYNTHETIC_DATA"
    assert analysis.narrative_warning and "no LLM API was called" in analysis.narrative_warning


def test_ai_analysis_fails_closed_when_no_narrative_is_permitted(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(terminal.TerminalError):
        terminal.get_ai_analysis(SYMBOL, allow_synthetic_narrative=False)


def test_ai_analysis_for_an_unknown_symbol_fails_closed():
    with pytest.raises(terminal.TerminalError):
        terminal.get_ai_analysis("999999.XX")


# --- UI boundary ---------------------------------------------------------------------------------------------

def test_ui_reaches_project_code_only_through_application_layer_modules():
    tree = ast.parse(_source(UI_FILE), filename=UI_FILE)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.update(f"{node.module}.{a.name}" for a in node.names)
            imported.add(node.module)
    project = {m for m in imported if m.startswith("src.") and m != "src.app"}
    assert project == {
        "src.app.research_application",
        "src.app.research_analyst_application",
        "src.app.terminal_application",
    }


def test_terminal_application_imports_no_ui_framework():
    tree = ast.parse(_source(TERMINAL_APP_FILE))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    assert not (modules & {"streamlit", "flask", "fastapi", "jinja2"})


def test_terminal_ui_exposes_no_internal_vocabulary():
    """A Terminal user must not see PIT / hash / evidence id / research identity. Only the
    Terminal branch of the UI file is inspected — Research mode legitimately uses those words."""
    source = _source(UI_FILE)
    start = source.index('if mode == "Terminal":')
    end = source.index("else:\n    st.title(\"📊 Research Workbench\")")
    terminal_branch = source[start:end]
    for internal in ("evidence_bundle_hash", "evidence_id", "PIT", "research_run_id",
                     "reproducibility_scope", "result_hash", "prompt_version"):
        assert internal not in terminal_branch


def test_terminal_is_the_default_mode():
    source = _source(UI_FILE)
    assert 'st.sidebar.radio("模式", ["Terminal", "Research"], index=0)' in source


def test_research_mode_is_retained():
    source = _source(UI_FILE)
    for page in ("New Research Run", "Research Run History", "AI Research Analyst"):
        assert page in source
