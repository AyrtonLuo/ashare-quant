"""
app.py
Ashare Quant Pro - A-share research, risk, and paper trading workstation.
"""

import os
import sys
from typing import Dict, Iterable, List, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Keep the project root importable when Streamlit launches this file directly.
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.analysis.stock_f10_engine import get_valuation_metrics
from src.data.akshare_engine import fetch_realtime_quotes, fetch_stock_news
from src.data.akshare_provider import AkShareProvider
from src.data.realtime_engine import fetch_global_indices_snapshot
from src.execution.paper_trader import PaperAccount
from src.strategy.risk_engine import DynamicCapitalAllocator


@st.cache_resource
def get_market_provider():
    return AkShareProvider()



APP_TITLE = "Ashare Quant Pro"
DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "data")

DEFAULT_TARGETS = [
    {"symbol": "600519", "name": "贵州茅台", "target_weight_pct": 18.0},
    {"symbol": "000001", "name": "平安银行", "target_weight_pct": 18.0},
    {"symbol": "600690", "name": "海尔智家", "target_weight_pct": 18.0},
    {"symbol": "300308", "name": "中际旭创", "target_weight_pct": 15.0},
    {"symbol": "600398", "name": "海澜之家", "target_weight_pct": 15.0},
]


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="AQ",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
<style>
    :root {
        --aq-bg: #f5f7fa;
        --aq-surface: #ffffff;
        --aq-border: #d8e0ea;
        --aq-text: #17202a;
        --aq-muted: #687385;
        --aq-red: #d92d20;
        --aq-green: #039855;
        --aq-amber: #b7791f;
        --aq-blue: #155eef;
        --aq-ink: #101828;
    }
    .stApp {
        background: var(--aq-bg);
        color: var(--aq-text);
    }
    .block-container {
        max-width: 1480px;
        padding-top: 1.25rem;
        padding-bottom: 2rem;
    }
    div[data-testid="stSidebar"] {
        background: #eef2f6;
        border-right: 1px solid var(--aq-border);
    }
    .aq-header {
        border: 1px solid var(--aq-border);
        border-radius: 8px;
        background: var(--aq-surface);
        padding: 18px 20px;
        margin-bottom: 18px;
    }
    .aq-kicker {
        color: var(--aq-muted);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0;
        text-transform: uppercase;
    }
    .aq-title {
        color: var(--aq-ink);
        font-size: 30px;
        line-height: 1.2;
        font-weight: 760;
        margin-top: 4px;
    }
    .aq-subtitle {
        color: var(--aq-muted);
        font-size: 14px;
        margin-top: 8px;
    }
    .aq-card {
        border: 1px solid var(--aq-border);
        border-top: 4px solid var(--accent);
        border-radius: 8px;
        background: var(--aq-surface);
        padding: 14px 16px;
        min-height: 118px;
    }
    .aq-label {
        color: var(--aq-muted);
        font-size: 12px;
        font-weight: 650;
    }
    .aq-value {
        color: var(--aq-ink);
        font-size: 24px;
        font-weight: 760;
        line-height: 1.3;
        margin-top: 5px;
    }
    .aq-note {
        color: var(--note-color);
        font-size: 12px;
        margin-top: 6px;
    }
    .aq-panel {
        border: 1px solid var(--aq-border);
        border-radius: 8px;
        background: var(--aq-surface);
        padding: 14px 16px;
        margin-bottom: 14px;
    }
    .aq-mini-card {
        border: 1px solid var(--aq-border);
        border-radius: 8px;
        background: var(--aq-surface);
        padding: 12px 14px;
        min-height: 86px;
    }
    .aq-mini-label {
        color: var(--aq-muted);
        font-size: 12px;
        font-weight: 650;
    }
    .aq-mini-value {
        color: var(--aq-ink);
        font-size: 22px;
        line-height: 1.25;
        font-weight: 760;
        margin-top: 8px;
        white-space: normal;
        overflow-wrap: anywhere;
    }
    .aq-section-title {
        color: var(--aq-ink);
        font-size: 17px;
        font-weight: 730;
        margin-bottom: 8px;
    }
    .aq-small {
        color: var(--aq-muted);
        font-size: 12px;
        line-height: 1.5;
    }
    div[data-testid="stMetric"] {
        border: 1px solid var(--aq-border);
        border-radius: 8px;
        background: var(--aq-surface);
        padding: 12px 14px;
    }
    div[data-testid="stMetric"] * {
        color: var(--aq-text) !important;
    }
    div[data-testid="stMetric"] label,
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] * {
        color: var(--aq-muted) !important;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid var(--aq-border);
        border-radius: 8px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border: 1px solid var(--aq-border);
        border-radius: 8px;
        background: var(--aq-surface);
        padding: 8px 14px;
    }
    .stTabs [data-baseweb="tab"] p {
        color: var(--aq-text) !important;
        font-weight: 650;
    }
    .stTabs [aria-selected="true"] p {
        color: var(--aq-red) !important;
    }
</style>
""",
    unsafe_allow_html=True,
)


def normalize_symbol(symbol: object) -> str:
    return str(symbol).strip().zfill(6)


def money(value: float) -> str:
    return f"¥ {float(value):,.2f}"


def pct(value: float) -> str:
    return f"{float(value):+.2f}%"


def render_header() -> None:
    st.markdown(
        f"""
        <div class="aq-header">
            <div class="aq-kicker">A-share quantitative workstation</div>
            <div class="aq-title">{APP_TITLE}</div>
            <div class="aq-subtitle">
                研究、风控、模拟调仓与新闻情报放在同一套工作流中，交易约束按 A 股 T+1、100 股一手、印花税与佣金口径执行。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, note: str, accent: str, note_color: str = "#687385") -> None:
    st.markdown(
        f"""
        <div class="aq-card" style="--accent: {accent}; --note-color: {note_color};">
            <div class="aq-label">{label}</div>
            <div class="aq-value">{value}</div>
            <div class="aq-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def mini_stat_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="aq-mini-card">
            <div class="aq-mini-label">{label}</div>
            <div class="aq-mini-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=10, show_spinner=False)
def load_realtime_quotes() -> pd.DataFrame:
    try:
        return fetch_realtime_quotes()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def load_global_indices() -> List[Dict[str, float]]:
    try:
        return fetch_global_indices_snapshot()
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def load_stock_news(symbol: str, max_items: int = 5) -> List[Dict[str, object]]:
    return fetch_stock_news(symbol, max_items=max_items)


@st.cache_data(ttl=300, show_spinner=False)
def load_local_latest_prices(symbols: Tuple[str, ...]) -> Dict[str, float]:
    prices: Dict[str, float] = {}
    for sym in symbols:
        for path in (
            os.path.join(DATA_DIR, "stocks", f"{sym}.parquet"),
            os.path.join(DATA_DIR, f"{sym}.parquet"),
        ):
            if not os.path.exists(path):
                continue
            try:
                df = pd.read_parquet(path, columns=["close"])
                if not df.empty:
                    price = float(df["close"].dropna().iloc[-1])
                    if price > 0:
                        prices[sym] = price
                        break
            except Exception:
                continue
    return prices


def build_price_map(symbols: Iterable[str], quotes: pd.DataFrame) -> Tuple[Dict[str, float], Dict[str, str]]:
    clean_symbols = tuple(sorted({normalize_symbol(sym) for sym in symbols if str(sym).strip()}))
    local_prices = load_local_latest_prices(clean_symbols)
    prices: Dict[str, float] = {sym: float(local_prices.get(sym, 10.0)) for sym in clean_symbols}
    source: Dict[str, str] = {sym: "local" if sym in local_prices else "fallback" for sym in clean_symbols}

    if quotes is not None and not quotes.empty and "代码" in quotes.columns:
        q = quotes.copy()
        q["代码"] = q["代码"].astype(str).str.zfill(6)
        q = q[q["代码"].isin(clean_symbols)]
        for _, row in q.iterrows():
            try:
                price = float(row.get("最新价", 0.0))
            except (TypeError, ValueError):
                price = 0.0
            if price > 0:
                sym = str(row["代码"]).zfill(6)
                prices[sym] = price
                source[sym] = "realtime"

    return prices, source


def default_target_frame() -> pd.DataFrame:
    return pd.DataFrame(DEFAULT_TARGETS)


def sanitize_target_frame(raw_df: pd.DataFrame) -> pd.DataFrame:
    if raw_df is None or raw_df.empty:
        return default_target_frame()

    df = raw_df.copy()
    df["symbol"] = df["symbol"].map(normalize_symbol)
    df["name"] = df["name"].fillna("").astype(str).str.strip()
    df["name"] = df.apply(lambda row: row["symbol"] if not row["name"] else row["name"], axis=1)
    df["target_weight_pct"] = pd.to_numeric(df["target_weight_pct"], errors="coerce").fillna(0.0)
    df = df[df["symbol"].str.len() == 6]
    df = df.drop_duplicates(subset=["symbol"], keep="last")
    df = df[df["target_weight_pct"] > 0]

    if df.empty:
        return default_target_frame()
    return df.reset_index(drop=True)


def build_target_plan(
    target_df: pd.DataFrame,
    price_map: Dict[str, float],
    source_map: Dict[str, str],
    account: PaperAccount,
    summary: Dict[str, object],
    market_regime: Dict[str, object],
) -> pd.DataFrame:
    df = sanitize_target_frame(target_df)
    weight_sum = float(df["target_weight_pct"].sum())
    if weight_sum <= 0:
        df["target_weight"] = 1.0 / len(df)
    else:
        df["target_weight"] = df["target_weight_pct"] / weight_sum

    allowed_equity = float(summary["total_equity"]) * float(market_regime["equity_cap_pct"]) / 100.0
    rows = []
    for _, row in df.iterrows():
        sym = normalize_symbol(row["symbol"])
        latest = float(price_map.get(sym, 10.0))
        target_weight = float(row["target_weight"])
        target_value = allowed_equity * target_weight
        target_shares = int(target_value // (latest * 100)) * 100 if latest > 0 else 0
        expected_value = target_shares * latest
        current_shares = int(account.positions.get(sym, {}).get("shares", 0))
        delta_shares = target_shares - current_shares

        rows.append(
            {
                "symbol": sym,
                "name": str(row["name"]),
                "close": round(latest, 3),
                "target_weight": target_weight,
                "目标权重 %": round(target_weight * 100.0, 2),
                "目标市值 (CNY)": round(target_value, 2),
                "目标持股 (100股整)": target_shares,
                "当前持股": current_shares,
                "调仓股数": delta_shares,
                "预计持仓市值": round(expected_value, 2),
                "价格来源": source_map.get(sym, "fallback"),
            }
        )
    return pd.DataFrame(rows)


def build_execution_frame(target_plan: pd.DataFrame, account: PaperAccount, price_map: Dict[str, float]) -> pd.DataFrame:
    execution_df = target_plan[["symbol", "name", "close", "target_weight"]].copy()
    target_symbols = set(execution_df["symbol"].tolist())

    exit_rows = []
    for sym, pos in account.positions.items():
        clean_sym = normalize_symbol(sym)
        if clean_sym in target_symbols:
            continue
        exit_rows.append(
            {
                "symbol": clean_sym,
                "name": str(pos.get("name", clean_sym)),
                "close": float(price_map.get(clean_sym, pos.get("cost_price", 10.0))),
                "target_weight": 0.0,
            }
        )

    if exit_rows:
        execution_df = pd.concat([execution_df, pd.DataFrame(exit_rows)], ignore_index=True)
    return execution_df


def extract_shanghai_index(indices: List[Dict[str, object]]) -> float:
    for idx in indices:
        if "上证" in str(idx.get("name", "")):
            try:
                return float(idx.get("price", 3300.0))
            except (TypeError, ValueError):
                return 3300.0
    return 3300.0


def render_sidebar(account: PaperAccount, sh_price: float) -> Tuple[Dict[str, object], bool, bool]:
    st.sidebar.markdown("### 控制台")

    auto_refresh = st.sidebar.toggle("自动刷新行情", value=True)
    refresh_seconds = st.sidebar.slider("刷新间隔", min_value=5, max_value=60, value=15, step=5)
    use_live_quotes = st.sidebar.toggle("启用实时行情源", value=False)

    if auto_refresh:
        try:
            from streamlit_autorefresh import st_autorefresh

            st_autorefresh(interval=refresh_seconds * 1000, key="aq_refresh")
        except Exception:
            pass

    st.sidebar.markdown("### 账户")
    reset_capital = st.sidebar.number_input("重置资金", min_value=10000.0, value=1000000.0, step=10000.0)
    if st.sidebar.button("重置模拟账户", use_container_width=True):
        account.reset_account(float(reset_capital))
        st.session_state["paper_account"] = account
        st.success("模拟账户已重置。")
        st.rerun()

    st.sidebar.markdown("### 大盘风控")
    index_p = st.sidebar.number_input("上证指数当前价", value=float(sh_price), step=10.0)
    index_ma20 = st.sidebar.number_input("上证指数 MA20", value=float(sh_price * 0.98), step=10.0)
    market_vol = st.sidebar.number_input("沪深两市成交额(亿元)", value=9200.0, step=500.0)

    allocator = DynamicCapitalAllocator(
        index_price=index_p,
        index_ma20=index_ma20,
        market_volume_yi=market_vol,
    )
    return allocator.evaluate_market_regime(), auto_refresh, use_live_quotes


def render_overview(summary: Dict[str, object], market_regime: Dict[str, object], source_map: Dict[str, str]) -> None:
    pnl_color = "#d92d20" if float(summary["pnl_pct"]) >= 0 else "#039855"
    regime_color = str(market_regime.get("color", "#155eef"))

    cols = st.columns(4)
    with cols[0]:
        metric_card("账户总资产", money(float(summary["total_equity"])), f"累计收益 {pct(float(summary['pnl_pct']))}", "#155eef", pnl_color)
    with cols[1]:
        cash_pct = float(summary["cash"]) / max(float(summary["total_equity"]), 1.0) * 100.0
        metric_card("可用现金", money(float(summary["cash"])), f"现金占比 {cash_pct:.1f}%", "#b7791f")
    with cols[2]:
        stock_pct = float(summary["market_value"]) / max(float(summary["total_equity"]), 1.0) * 100.0
        metric_card("持仓市值", money(float(summary["market_value"])), f"股票仓位 {stock_pct:.1f}%", "#d92d20")
    with cols[3]:
        metric_card("大盘模式", str(market_regime["regime"]), f"股票仓位上限 {market_regime['equity_cap_pct']:.0f}%", regime_color)

    chart_col, risk_col = st.columns([1.05, 1.95])
    with chart_col:
        values = [float(summary["market_value"]), float(summary["cash"])]
        fig = go.Figure(
            data=[
                go.Pie(
                    labels=["股票持仓", "避险现金"],
                    values=values,
                    hole=0.56,
                    marker_colors=["#d92d20", "#b7791f"],
                    textinfo="label+percent",
                )
            ]
        )
        fig.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=20, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#17202a"),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with risk_col:
        st.markdown(
            f"""
            <div class="aq-panel">
                <div class="aq-section-title">市场风控</div>
                <div class="aq-small">{market_regime['advice']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            mini_stat_card("上证指数", f"{market_regime['index_price']:,.2f}")
        with c2:
            mini_stat_card("MA20", f"{market_regime['index_ma20']:,.2f}")
        with c3:
            mini_stat_card("两市成交额", f"{market_regime['market_volume_yi']:,.0f} 亿")
        with c4:
            mini_stat_card("单股上限", f"{market_regime['max_single_stock_pct']:.0f}%")

        source_counts = pd.Series(source_map).value_counts().to_dict() if source_map else {}
        st.caption(
            "行情来源: "
            + " / ".join([f"{name} {count}" for name, count in source_counts.items()])
            + f" | 更新时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )


def render_rebalance(
    account: PaperAccount,
    summary: Dict[str, object],
    market_regime: Dict[str, object],
    quotes: pd.DataFrame,
    initial_price_map: Dict[str, float],
) -> pd.DataFrame:
    st.markdown("#### 目标组合")
    editable = st.data_editor(
        default_target_frame(),
        key="target_editor",
        hide_index=True,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "symbol": st.column_config.TextColumn("代码", required=True, width="small"),
            "name": st.column_config.TextColumn("名称", required=True, width="medium"),
            "target_weight_pct": st.column_config.NumberColumn(
                "目标权重 %",
                min_value=0.0,
                max_value=100.0,
                step=0.5,
                format="%.2f",
            ),
        },
    )
    target_seed = sanitize_target_frame(editable)
    all_symbols = set(target_seed["symbol"].tolist()) | set(account.positions.keys())
    price_map, source_map = build_price_map(all_symbols, quotes)
    price_map.update({sym: initial_price_map.get(sym, price) for sym, price in price_map.items()})

    target_plan = build_target_plan(target_seed, price_map, source_map, account, summary, market_regime)

    st.markdown("#### 调仓预演")
    display_cols = [
        "symbol",
        "name",
        "close",
        "目标权重 %",
        "目标市值 (CNY)",
        "目标持股 (100股整)",
        "当前持股",
        "调仓股数",
        "预计持仓市值",
        "价格来源",
    ]
    st.dataframe(target_plan[display_cols], use_container_width=True, hide_index=True)

    expected_stock_value = float(target_plan["预计持仓市值"].sum()) if not target_plan.empty else 0.0
    expected_cash = max(0.0, float(summary["total_equity"]) - expected_stock_value)
    c1, c2, c3 = st.columns(3)
    c1.metric("预计股票市值", money(expected_stock_value))
    c2.metric("预计保留现金", money(expected_cash))
    c3.metric("目标股数合计", f"{int(target_plan['目标持股 (100股整)'].sum()):,} 股")

    if st.button("执行模拟调仓", type="primary", use_container_width=True):
        execution_df = build_execution_frame(target_plan, account, price_map)
        result = account.rebalance(execution_df, market_regime_info=market_regime)
        st.session_state["paper_account"] = account
        orders = result.get("executed_orders", [])
        if orders:
            st.success(f"已撮合 {len(orders)} 笔模拟订单。")
        else:
            st.info("当前持仓与目标组合已基本一致。")
        st.rerun()

    return target_plan


def render_positions(summary: Dict[str, object]) -> None:
    positions_df = summary["positions_df"]
    logs_df = summary["trade_logs_df"]

    st.markdown("#### 当前持仓")
    if positions_df.empty:
        st.info("当前模拟账户暂无持仓。")
    else:
        st.dataframe(positions_df, use_container_width=True, hide_index=True)

    st.markdown("#### 交易流水")
    if logs_df.empty:
        st.caption("暂无交易记录。")
    else:
        st.dataframe(logs_df, use_container_width=True, hide_index=True)


def render_intelligence(target_plan: pd.DataFrame, summary: Dict[str, object]) -> None:
    positions_df = summary["positions_df"]
    symbols = set(target_plan["symbol"].tolist()) if target_plan is not None and not target_plan.empty else set()
    if not positions_df.empty and "股票代码" in positions_df.columns:
        symbols.update(positions_df["股票代码"].astype(str).str.zfill(6).tolist())

    if not symbols:
        st.info("暂无可查看标的。")
        return

    selected = st.selectbox("标的", sorted(symbols))
    valuation = get_valuation_metrics(selected)
    c1, c2, c3 = st.columns(3)
    c1.metric("PE-TTM", f"{valuation['pe_ttm']} 倍")
    c2.metric("PB", f"{valuation['pb']} 倍")
    c3.metric("估值百分位", str(valuation["percentile_str"]))

    if st.button("加载新闻情报", use_container_width=True):
        st.session_state["news_symbol"] = selected

    if st.session_state.get("news_symbol") == selected:
        with st.spinner("正在读取新闻..."):
            news_items = load_stock_news(selected, max_items=5)
        for item in news_items:
            title = item.get("title", "")
            date = item.get("date", "")
            sentiment = item.get("sentiment", "中性")
            source = item.get("source", "")
            url = item.get("url", "")
            with st.expander(f"[{date}] [{sentiment}] {title}", expanded=False):
                st.write(item.get("content", ""))
                st.caption(str(source))
                if url:
                    st.link_button("打开原文", str(url))


def main() -> None:
    if "paper_account" not in st.session_state:
        st.session_state["paper_account"] = PaperAccount(initial_capital=1000000.0)

    account: PaperAccount = st.session_state["paper_account"]
    indices = load_global_indices()
    sh_price = extract_shanghai_index(indices)
    market_regime, _, use_live_quotes = render_sidebar(account, sh_price)

    base_symbols = {item["symbol"] for item in DEFAULT_TARGETS} | set(account.positions.keys())
    quotes = load_realtime_quotes() if use_live_quotes else pd.DataFrame()
    price_map, source_map = build_price_map(base_symbols, quotes)
    summary = account.get_summary(price_map)
    render_header()

    overview_tab, rebalance_tab, positions_tab, intel_tab = st.tabs(["总览", "调仓", "持仓", "情报"])

    with overview_tab:
        render_overview(summary, market_regime, source_map)

    with rebalance_tab:
        target_plan = render_rebalance(account, summary, market_regime, quotes, price_map)

    with positions_tab:
        render_positions(summary)

    with intel_tab:
        if "target_plan_cache" not in st.session_state:
            st.session_state["target_plan_cache"] = pd.DataFrame()
        render_intelligence(
            target_plan if "target_plan" in locals() else st.session_state["target_plan_cache"],
            summary,
        )

    if "target_plan" in locals():
        st.session_state["target_plan_cache"] = target_plan


if __name__ == "__main__":
    main()
