"""
app.py
A 股模拟跟投与动态仓位调仓控制台 (Lean A-Share Paper Trading Console)
极简架构：
1. 【📊 账户资产与大盘风控】
2. 【⚡ 智能跟投与一键调仓预演】
3. 【📦 当前持仓与交易日志】
"""

import os
import sys
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.data.akshare_engine import get_single_stock_spot, fetch_stock_news
from src.data.realtime_engine import fetch_global_indices_snapshot
from src.data.symbol_utils import normalize_ashare_code
from src.strategy.risk_engine import DynamicCapitalAllocator
from src.execution.paper_trader import PaperAccount
from src.analysis.stock_f10_engine import get_valuation_metrics

# 页面基础配置 (宽屏)
st.set_page_config(
    page_title="A股模拟跟投与动态仓位控制台",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 确保清除旧脏缓存，使最新规则即刻生效
st.cache_data.clear()

# 自定义金融终端 CSS 样式 (适配 A 股：红涨绿跌)
st.markdown("""
<style>
    .metric-card-red {
        background-color: rgba(255, 51, 51, 0.08);
        border-left: 5px solid #FF3333;
        padding: 14px 18px;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    .metric-card-green {
        background-color: rgba(0, 230, 118, 0.08);
        border-left: 5px solid #00E676;
        padding: 14px 18px;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    .metric-card-yellow {
        background-color: rgba(255, 213, 79, 0.08);
        border-left: 5px solid #FFD54F;
        padding: 14px 18px;
        border-radius: 8px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# 尝试引入 autorefresh (1500ms)
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=1500, key="datarefresh")
except Exception:
    pass


def main():
    st.title("⚡ A股模拟跟投与动态仓位控制台")
    st.caption("基于 AkShare 官方 API 标准接口 | A股 T+1 规则 | 100 股向下取整 | 动态大盘避险资金分配器")

    # 初始化模拟盘账户
    if "paper_account" not in st.session_state:
        st.session_state["paper_account"] = PaperAccount(initial_capital=1000000.0)

    account = st.session_state["paper_account"]

    # 1. 侧边栏：大盘环境配置与账户管理
    st.sidebar.markdown("### ⚙️ 控制台设置")
    if st.sidebar.button("🔄 重置模拟账户 (100 万元初始金)", use_container_width=True):
        account.reset_account(1000000.0)
        st.session_state["paper_account"] = account
        st.success("账户已重置为 1,000,000.00 元现金！")
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 📈 大盘风控环境参数")

    indices = fetch_global_indices_snapshot()
    sh_price = 3300.0
    for idx in indices:
        if "上证" in idx.get("name", ""):
            sh_price = idx.get("price", 3300.0)

    index_p = st.sidebar.number_input("上证指数当前价", value=float(sh_price), step=10.0)
    index_ma20 = st.sidebar.number_input("上证指数 MA20 均线", value=float(sh_price * 0.98), step=10.0)
    market_vol = st.sidebar.number_input("沪深两市成交额 (亿元)", value=9200.0, step=500.0)

    # 计算大盘风控状态
    allocator = DynamicCapitalAllocator(index_price=index_p, index_ma20=index_ma20, market_volume_yi=market_vol)
    market_regime = allocator.evaluate_market_regime()

    # 包含最新价格的报价字典
    current_prices = {}
    for sym in list(account.positions.keys()) + ["600519", "000001", "600690", "300308", "600398"]:
        spot = get_single_stock_spot(sym)
        current_prices[sym] = spot.get("price", 10.0)

    summary = account.get_summary(current_prices)

    # ----------------------------------------------------
    # 板块一：【📊 账户资产与大盘风控】
    # ----------------------------------------------------
    st.markdown("### 【📊 账户资产与大盘风控】")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        pnl_col = "red" if summary["pnl_pct"] >= 0 else "green"
        st.markdown(f"""
        <div class="metric-card-{pnl_col}">
            <div style="font-size: 13px; color: #888;">账户总资产 (CNY)</div>
            <div style="font-size: 24px; font-weight: bold;">¥ {summary['total_equity']:,.2f}</div>
            <div style="font-size: 12px; color: {'#FF3333' if summary['pnl_pct']>=0 else '#00E676'};">
                累计收益率: {summary['pnl_pct']:+.2f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card-yellow">
            <div style="font-size: 13px; color: #888;">可用现金 (CNY)</div>
            <div style="font-size: 24px; font-weight: bold; color: #FFD54F;">¥ {summary['cash']:,.2f}</div>
            <div style="font-size: 12px; color: #888;">现金占比: {summary['cash']/(summary['total_equity'] if summary['total_equity']>0 else 1.0)*100:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card-red">
            <div style="font-size: 13px; color: #888;">持仓市值 (CNY)</div>
            <div style="font-size: 24px; font-weight: bold;">¥ {summary['market_value']:,.2f}</div>
            <div style="font-size: 12px; color: #888;">股票仓位: {summary['market_value']/(summary['total_equity'] if summary['total_equity']>0 else 1.0)*100:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        reg_col = "red" if "强势" in market_regime['regime'] else ("yellow" if "盘整" in market_regime['regime'] else "green")
        st.markdown(f"""
        <div class="metric-card-{reg_col}">
            <div style="font-size: 13px; color: #888;">大盘风控模式</div>
            <div style="font-size: 22px; font-weight: bold;">{market_regime['regime']}</div>
            <div style="font-size: 12px; color: #888;">建议保留现金: {market_regime['cash_reserve_pct']:.0f}%</div>
        </div>
        """, unsafe_allow_html=True)

    # 资产配比与风控图表
    chart_col1, chart_col2 = st.columns([1, 2])
    with chart_col1:
        labels = ['股票持仓市值', '避险现金储备']
        values = [summary['market_value'], summary['cash']]
        fig_donut = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=.5,
            marker_colors=['#FF3333', '#FFD54F']
        )])
        fig_donut.update_layout(
            title_text="资产分配比例 (股票 vs 避险现金)",
            template="plotly_dark",
            height=260,
            margin=dict(l=10, r=10, t=40, b=10),
            showlegend=True
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with chart_col2:
        st.info(f"💡 **风控与仓位建议**: {market_regime['advice']}")
        st.caption(f"当前指数: `{market_regime['index_price']}` | MA20: `{market_regime['index_ma20']}` | 两市成交: `{market_regime['market_volume_yi']} 亿元` | 股票持仓上限: `{market_regime['equity_cap_pct']}%` | 单股仓位上限: `{market_regime['max_single_stock_pct']}%`")

    st.markdown("---")

    # ----------------------------------------------------
    # 板块二：【⚡ 智能跟投与一键调仓预演】
    # ----------------------------------------------------
    st.markdown("### 【⚡ 智能跟投与一键调仓预演】")

    target_stocks = [
        {"symbol": "600519", "name": "贵州茅台", "target_weight": 0.18},
        {"symbol": "000001", "name": "平安银行", "target_weight": 0.18},
        {"symbol": "600690", "name": "海尔智家", "target_weight": 0.18},
        {"symbol": "300308", "name": "中际旭创", "target_weight": 0.15},
        {"symbol": "600398", "name": "海澜之家", "target_weight": 0.15}
    ]

    target_df = pd.DataFrame(target_stocks)

    target_df['最新价'] = target_df['symbol'].apply(lambda s: current_prices.get(s, 10.0))
    allowed_equity = summary['total_equity'] * (market_regime['equity_cap_pct'] / 100.0)

    target_df['目标市值 (CNY)'] = (allowed_equity * target_df['target_weight']).round(2)
    target_df['目标持股 (100股整)'] = (target_df['目标市值 (CNY)'] // (target_df['最新价'] * 100) * 100).astype(int)
    target_df['目标权重 %'] = (target_df['target_weight'] * 100.0).round(1)

    col_btn, col_txt = st.columns([1, 3])
    with col_btn:
        if st.button("⚡ 智能跟投：一键按动态仓位自动调仓", type="primary", use_container_width=True):
            res = account.rebalance(target_df, market_regime_info=market_regime)
            st.session_state["paper_account"] = account
            orders = res.get("executed_orders", [])
            if orders:
                st.success(f"🎉 调仓成功！共自动撮合完成 {len(orders)} 笔 A 股订单。")
            else:
                st.info("当前持仓已精准符合目标风控仓位，无需重复调仓。")
            st.rerun()

    with col_txt:
        st.caption(f"根据当前风控模式 `{market_regime['regime']}`，股票总仓位上限被控制在 **{market_regime['equity_cap_pct']}%**，单股风控上限 **<= 20%**，买卖自动按 **100 股 (1手)** 取整。")

    st.dataframe(target_df[['symbol', 'name', '最新价', '目标权重 %', '目标市值 (CNY)', '目标持股 (100股整)']], use_container_width=True)

    st.markdown("---")

    # ----------------------------------------------------
    # 板块三：【📦 当前持仓与交易日志】
    # ----------------------------------------------------
    st.markdown("### 【📦 当前持仓与交易日志】")

    pos_df = summary["positions_df"]
    if pos_df.empty:
        st.info("💡 当前模拟账户尚无持仓。请点击上方【⚡ 智能跟投：一键按动态仓位自动调仓】大按钮体验一键交易。")
    else:
        st.markdown("##### 💼 模拟盘实时持仓明细 (恪守 T+1 规则与印花税)")
        st.dataframe(pos_df, use_container_width=True)

        selected_sym = st.selectbox("选择持仓标的深入查看实时新闻 Feed 与估值:", pos_df['股票代码'].tolist())
        if selected_sym:
            v_info = get_valuation_metrics(selected_sym)
            st.caption(f"估值速览: PE-TTM `{v_info['pe_ttm']} 倍` | PB `{v_info['pb']} 倍` | 估值百分位 `{v_info['percentile_str']}`")

            news_items = fetch_stock_news(selected_sym, max_items=5)
            st.markdown(f"**📰 [{selected_sym}] 真实新闻文章 Feed 流:**")
            for item in news_items:
                t_title = item.get("title", "")
                t_date = item.get("date", "")
                t_sent = item.get("sentiment", "⚪ 中性")
                t_url = item.get("url", "")
                t_content = item.get("content", "")

                with st.expander(f"📰 [{t_date}] 【{t_sent}】 {t_title}", expanded=False):
                    st.write(t_content)
                    st.markdown(f'<a href="{t_url}" target="_blank" style="display: inline-block; background-color: #1e88e5; color: white; padding: 4px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; margin-top: 6px;">🔗 点击查看新闻原文 ↗</a>', unsafe_allow_html=True)

    # 交易历史日志
    st.markdown("##### 📜 调仓交易流水日志")
    logs_df = summary["trade_logs_df"]
    if not logs_df.empty:
        st.dataframe(logs_df, use_container_width=True)
    else:
        st.caption("暂无交易日志记录。")


if __name__ == "__main__":
    main()
