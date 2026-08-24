"""
test_terminal_ui_polish.py — consumer UI polish for the Terminal (信息层级 / 单位 / 红涨绿跌 /
AI 未开通提示). The honesty guarantees this polish must NOT weaken — REAL/DEMO isolation and
暂无数据-with-reason — are asserted again here against the polished source.
"""

import ast
import os

import pytest

from src.app import terminal_application as terminal

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "app")
UI_FILE = os.path.join(APP_DIR, "streamlit_app.py")
SYMBOL = "600519.SH"


def _source():
    with open(UI_FILE, "r") as f:
        return f.read()


def _terminal_branch():
    source = _source()
    start = source.index('if mode == "Terminal":')
    end = source.index("else:\n    st.title(\"📊 Research Workbench\")")
    return source[start:end]


# --- humanized units --------------------------------------------------------------------------

@pytest.mark.parametrize("shares,expected", [
    (119902495, "119.90万手"),   # 1手 = 100股
    (1000000, "1.00万手"),
    (50000, "500手"),
    (0, "0手"),
])
def test_volume_is_humanized_in_lots(shares, expected):
    assert terminal.humanize_volume(shares) == expected


@pytest.mark.parametrize("yuan,expected", [
    (1383380014, "13.83亿元"),
    (105000, "10.50万元"),
    (999, "999元"),
])
def test_amount_is_humanized(yuan, expected):
    assert terminal.humanize_amount(yuan) == expected


def test_humanizers_reject_negative_input():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        terminal.humanize_volume(-1)
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        terminal.humanize_amount(-1)


def test_humanizing_never_alters_the_underlying_view_value():
    quote = terminal.get_quote_view(SYMBOL, terminal.QUOTE_SOURCE_DEMO)
    assert quote.volume == 1000000.0          # the raw share count stays on the view


# --- the technical tally is a count, never a verdict --------------------------------------------

def test_summarize_technicals_tallies_labels_in_first_seen_order():
    readings = terminal.get_technical_views(SYMBOL, terminal.QUOTE_SOURCE_DEMO)
    summary = terminal.summarize_technicals(readings)
    for reading in readings:
        if reading.available:
            assert reading.plain_reading in summary
    assert f"{terminal.NOT_AVAILABLE_TEXT} 1 项" in summary   # demo MACD is honestly short


def test_summarize_technicals_contains_no_advice_language():
    summary = terminal.summarize_technicals(
        terminal.get_technical_views(SYMBOL, terminal.QUOTE_SOURCE_DEMO))
    for forbidden in ("买入", "卖出", "建议", "目标价", "满仓", "清仓", "综合评分"):
        assert forbidden not in summary


def test_summarize_technicals_of_nothing_is_not_available():
    assert terminal.summarize_technicals([]) == terminal.NOT_AVAILABLE_TEXT


# --- AI availability gate ------------------------------------------------------------------------

def test_ai_unavailable_without_any_credential(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert terminal.is_ai_available() is False


def test_ai_available_with_a_credential(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gm-not-a-real-key-0123456789")
    assert terminal.is_ai_available() is True


def test_the_unavailable_notice_is_honest_not_a_placeholder():
    assert "暂未开通" in terminal.AI_UNAVAILABLE_NOTICE
    assert "尚未配置大模型服务" in terminal.AI_UNAVAILABLE_NOTICE


def test_the_ui_gates_the_ai_tab_on_availability():
    branch = _terminal_branch()
    assert "terminal.is_ai_available()" in branch
    assert "terminal.AI_UNAVAILABLE_NOTICE" in branch


# --- layout: tabs, sidebar source, A股 colours ------------------------------------------------------

def test_the_page_uses_tabs_for_its_sections():
    branch = _terminal_branch()
    assert "st.tabs(" in branch
    for tab in ("行情走势", "技术面", "基本面", "最新消息", "AI 分析"):
        assert tab in branch


def test_the_data_source_selector_lives_in_the_sidebar():
    assert 'st.sidebar.radio(\n        "数据源"' in _terminal_branch()


def test_price_change_uses_a_share_colour_convention():
    """A股红涨绿跌 — st.metric's default is the US green-up, so delta_color must be inverse."""
    assert 'delta_color="inverse"' in _source()


def test_search_has_a_consumer_placeholder():
    assert "600519 / 茅台" in _terminal_branch()


# --- the polish must not have weakened the honesty guarantees ----------------------------------------

def test_terminal_branch_still_exposes_no_internal_vocabulary():
    branch = _terminal_branch()
    for internal in ("evidence_bundle_hash", "evidence_id", "PIT", "research_run_id",
                     "reproducibility_scope", "result_hash", "prompt_version"):
        assert internal not in branch


def test_the_demo_badge_and_source_labels_survive_the_polish():
    source = _source()
    assert "quote.data_status" in source
    assert "quote.demo_notice" in source
    assert "panel.data_source" in source          # fundamentals + news still name their feeds
    assert "history.data_source" in source


def test_missing_fundamental_reasons_survive_the_polish():
    """Reasons moved into an expander but must still be rendered, row by row."""
    source = _source()
    assert "row.reason" in source
    # The UI references the shared constant rather than hardcoding the string — asserting the
    # reference, not the literal, is the correct check.
    assert "terminal.NOT_AVAILABLE_TEXT" in source


def test_the_disclaimer_survives_the_polish():
    branch = _terminal_branch()
    assert "terminal.DISCLAIMER" in branch
    assert "stock.disclaimer" in branch
