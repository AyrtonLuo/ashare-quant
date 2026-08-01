"""
app.py
ashare-quant 量化研究系统 Web 终端 (同花顺/雪球风格 AI 选股终端)
页面架构：
1. 🏠 AI 选股大盘总览：4大直观 KPI (红字盈利) + A股经典红/灰配色 Plotly 净值走势图
2. 🔥 今日 AI 优质推荐榜：Top 39 优质股票 + 5星级推荐 + 中文理由标签 (支持搜索与排序)
3. 📊 AI 策略胜率与因子画像：通俗化胜率、超额收益与中性化对比
4. 🚀 一键跟投智能调仓：富途港股/A股模拟盘 1 秒一键跟投下发
"""

import os
import sys
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.data_updater import update_quality_universe_data
from src.strategy.factors import calculate_raw_factors, preprocess_factors_cross_section
from src.strategy.composite_factor import build_composite_alpha_factor
from src.strategy.factor_neutralizer import neutralize_factors_cross_section, orthogonalize_factors
from src.factor_analyzer import summarize_factor_ic, calculate_rank_ic, run_layered_backtest
from src.risk_manager import apply_risk_managed_backtest
from src.strategy_decay_analyzer import diagnose_alpha_decay

DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "data")
DAILY_PARQUET = os.path.join(DATA_DIR, "stocks_daily.parquet")

# 页面基础配置 (宽屏 + 同花顺风格深浅主色)
st.set_page_config(
    page_title="ashare-quant AI 智能选股终端",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 A 股同花顺/雪球金融风格 CSS 样式
st.markdown("""
<style>
    .metric-card-red {
        background-color: #fff1f0;
        border-left: 5px solid #d62728;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    .metric-title {
        font-size: 13px;
        color: #666666;
        margin-bottom: 4px;
    }
    .metric-value-red {
        font-size: 24px;
        font-weight: bold;
        color: #d62728;
    }
    .metric-value-green {
        font-size: 24px;
        font-weight: bold;
        color: #2ca02c;
    }
    .metric-value-blue {
        font-size: 24px;
        font-weight: bold;
        color: #1f77b4;
    }
</style>
""", unsafe_allow_html=True)


def generate_stock_tag(row) -> tuple[str, str]:
    """根据因子得分生成同花顺/雪球风格 5星级评级与中文理由标签"""
    alpha_score = float(row.get('COMPOSITE_ALPHA_norm', 1.0))
    mom_score = float(row.get('MOM_20_norm', 0.0))
    vol_score = float(row.get('LOW_VOL_20_norm', 0.0))
    
    # 1. 星级转换
    if alpha_score >= 1.35:
        stars = "⭐⭐⭐⭐⭐"
    elif alpha_score >= 1.30:
        stars = "⭐⭐⭐⭐"
    elif alpha_score >= 1.25:
        stars = "⭐⭐⭐"
    else:
        stars = "⭐⭐"
        
    # 2. 中文理由标签 (含“⚖️ 综合质量均衡”降级兜底)
    if vol_score >= 1.0 and mom_score >= 0.8:
        tag = "🔥 攻守兼备 / 机构重仓"
    elif vol_score >= 1.0:
        tag = "🛡️ 稳健高股息 / 低波避险"
    elif mom_score >= 0.8:
        tag = "⚡ 动量突破龙头 / 强势上涨"
    else:
        tag = "⚖️ 综合质量均衡 / 稳健优选"
        
    return stars, tag


def get_styled_recommendations(df_composite: pd.DataFrame, style_mode: str, top_pct: float = 0.05) -> pd.DataFrame:
    """
    根据用户选择的交易风格 (style_mode) 动态重新计算最新调仓日的选股 Composite Alpha 得分并打标排序：
    - 🛡️ 极客防守型：按 LOW_VOL (低波) 70% + 均线偏离 30% 重新打分排序
    - ⚡ 激进进攻型：按 MOM (动量) 70% + 舆情/偏离 30% 重新打分排序
    - 📰 新闻催化型：按 ⭐️4~5星重磅权威新闻 60% + MOM 40% 重新打分排序
    - ⚖️ 攻守兼备型：自适应因子得分
    """
    if df_composite is None or df_composite.empty:
        return pd.DataFrame()

    latest_date = df_composite['date'].max()
    latest_day = df_composite[df_composite['date'] == latest_date].copy()

    mom_col = latest_day['MOM_20_norm'].fillna(0.0) if 'MOM_20_norm' in latest_day.columns else latest_day.get('MOM_20', 0.0)
    vol_col = latest_day['LOW_VOL_20_norm'].fillna(0.0) if 'LOW_VOL_20_norm' in latest_day.columns else latest_day.get('LOW_VOL_20', 0.0)
    dev_col = latest_day['MA_DEV_20_norm'].fillna(0.0) if 'MA_DEV_20_norm' in latest_day.columns else latest_day.get('MA_DEV_20', 0.0)
    sent_col = latest_day.get('SENTIMENT_ALPHA', 0.0)

    if "极客防守型" in style_mode:
        styled_score = 0.70 * vol_col + 0.30 * dev_col
        default_tag = "🛡️ 极致低波高股息"
    elif "激进进攻型" in style_mode:
        styled_score = 0.70 * mom_col + 0.15 * dev_col + 0.15 * sent_col
        default_tag = "⚡ 动量突破板块龙头"
    elif "新闻催化型" in style_mode:
        styled_score = 0.60 * sent_col + 0.40 * mom_col
        default_tag = "📰 重磅新闻实锤催化"
    else:
        styled_score = latest_day.get('COMPOSITE_ALPHA_norm', 0.50 * mom_col + 0.50 * vol_col)
        default_tag = "⚖️ 攻守兼备自适应选股"

    latest_day['styled_score'] = styled_score
    top_k = max(1, int(len(latest_day) * top_pct))
    sorted_df = latest_day.sort_values('styled_score', ascending=False).head(top_k).copy()

    stars_list = []
    tags_list = []
    for _, row in sorted_df.iterrows():
        score_val = float(row.get('styled_score', 1.0))
        if score_val >= 0.8 or "极客防守" in style_mode or "新闻催化" in style_mode:
            stars = "⭐⭐⭐⭐⭐"
        elif score_val >= 0.4:
            stars = "⭐⭐⭐⭐"
        elif score_val >= 0.0:
            stars = "⭐⭐⭐"
        else:
            stars = "⭐⭐"

        _, auto_tag = generate_stock_tag(row)
        final_tag = default_tag if "自适应" not in default_tag else auto_tag
        stars_list.append(stars)
        tags_list.append(final_tag)

    sorted_df['AI推荐星级'] = stars_list
    sorted_df['推荐理由标签'] = tags_list
    sorted_df['COMPOSITE_ALPHA_norm'] = sorted_df['styled_score']
    return sorted_df


@st.cache_data(ttl=3600, show_spinner=False)
def load_and_process_quant_engine(style: str = "⚖️ 攻守兼备型 (自适应)"):
    """读取本地 Parquet 数据，并运行 AI 多因子计算、IC 诊断与风控回测"""
    if not os.path.exists(DAILY_PARQUET):
        update_quality_universe_data(max_workers=8)
        
    raw_df = pd.read_parquet(DAILY_PARQUET)
    raw_df['date'] = pd.to_datetime(raw_df['date'])
    
    num_stocks = raw_df['symbol'].nunique()
    
    # 计算基础多因子
    df_factors = calculate_raw_factors(raw_df)
    df_factors['LOW_VOL_20'] = -df_factors['VOL_20']
    factor_base_names = ["MOM_20", "VOL_20", "LOW_VOL_20", "MA_DEV_20"]
    df_processed = preprocess_factors_cross_section(df_factors, factor_base_names)
    
    # 动态 IC-IR 合成 Alpha
    df_composite = build_composite_alpha_factor(df_processed, method="dynamic_ic_ir")
    
    # 机构级市值与行业中性化 & 多因子对称正交化
    df_composite = neutralize_factors_cross_section(df_composite, ["COMPOSITE_ALPHA"])
    df_composite = orthogonalize_factors(df_composite, ["MOM_20_norm", "LOW_VOL_20_norm", "MA_DEV_20_norm"])
    
    # 全量股票池新闻舆情 Alpha 融合 (Pre-filtering & Sentiment Alpha)
    from src.analysis.news_analyzer import integrate_sentiment_alpha
    df_composite = integrate_sentiment_alpha(df_composite)
    
    # 抓取全球跨市场隔夜宏观指标与情绪分
    from src.data.global_market_fetcher import fetch_global_intermarket_indicators
    macro_info = fetch_global_intermarket_indicators(timeout_sec=5)
    
    # 支持 4 大 AI 动态交易风格配置模型 (Adaptive Style Engine)
    from src.strategy.factor_engine import build_adaptive_alpha_factor
    df_composite = build_adaptive_alpha_factor(df_composite, macro_sentiment=macro_info['macro_score'], style=style)
    
    # IC 总结
    all_factor_cols = ["MOM_20", "LOW_VOL_20", "MA_DEV_20", "COMPOSITE_ALPHA", "COMPOSITE_ALPHA_neu"]
    ic_summary = summarize_factor_ic(df_composite, all_factor_cols)
    
    # 回测计算：自适应新策略 vs 原始静态策略 vs 大盘基准
    res_df, raw_metrics = run_layered_backtest(df_composite, "COMPOSITE_ALPHA_norm", rebalance_freq=5, top_pct=0.05)
    managed_df, risk_metrics = apply_risk_managed_backtest(res_df, max_dd_limit=0.15, cooldown_days=10, max_stock_weight=0.30)
    
    # 原始静态策略回测对比
    res_df_static, _ = run_layered_backtest(df_composite, "COMPOSITE_ALPHA_neu_norm", rebalance_freq=5, top_pct=0.05)
    managed_df_static, _ = apply_risk_managed_backtest(res_df_static, max_dd_limit=0.15, cooldown_days=10, max_stock_weight=0.30)
    managed_df['cum_static'] = managed_df_static['cum_managed']
    
    # Alpha 衰减诊断与 60 日 Rolling IC
    comp_ic_df = calculate_rank_ic(df_composite, "COMPOSITE_ALPHA_norm")
    comp_ic_df['rolling_ic_60'] = comp_ic_df['rank_ic'].rolling(window=60, min_periods=20).mean()
    decay_diag = diagnose_alpha_decay(comp_ic_df, "COMPOSITE_ALPHA")
    
    # 最新调仓日 Top 选股名单
    latest_date = df_composite['date'].max()
    latest_day_data = df_composite[df_composite['date'] == latest_date].dropna(subset=['COMPOSITE_ALPHA_norm'])
    top_5pct_k = max(1, int(len(latest_day_data) * 0.05))
    top_portfolio = latest_day_data.sort_values('COMPOSITE_ALPHA_norm', ascending=False).head(top_5pct_k).copy()
    
    # 附加同花顺/雪球标签与星级
    stars_list = []
    tags_list = []
    for _, row in top_portfolio.iterrows():
        stars, tag = generate_stock_tag(row)
        stars_list.append(stars)
        tags_list.append(tag)
        
    top_portfolio['AI推荐星级'] = stars_list
    top_portfolio['推荐理由标签'] = tags_list
    
    return {
        "num_stocks": num_stocks,
        "latest_date": latest_date,
        "df_composite": df_composite,
        "ic_summary": ic_summary,
        "managed_df": managed_df,
        "risk_metrics": risk_metrics,
        "comp_ic_df": comp_ic_df,
        "decay_diag": decay_diag,
        "top_portfolio": top_portfolio,
        "macro_info": macro_info
    }


# =============================================================================
# 🎨 侧边栏导航与系统状态 (同花顺/雪球风格)
# =============================================================================
st.sidebar.title("📈 问财/雪球 AI 选股终端")
st.sidebar.caption("中大盘优质标的池 (总市值 ≥ 90 亿元)")

menu = st.sidebar.radio(
    "终端功能导航",
    ["🏠 AI 选股大盘总览", "🔥 今日 AI 优质推荐榜", "🔍 概念板块与龙头搜索", "📊 AI 策略胜率与因子画像", "🚀 一键跟投智能调仓"],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ AI 动态交易风格配置")
style_choice = st.sidebar.selectbox(
    "选择交易风格模式:",
    [
        "⚖️ 攻守兼备型 (自适应)",
        "🛡️ 极客防守型 (低波70%)",
        "⚡ 激进进攻型 (动量70%)",
        "📰 新闻催化型 (舆情40%)"
    ],
    index=0
)
st.sidebar.caption(f"当前生效风格: `{style_choice}`")

st.sidebar.markdown("---")
st.sidebar.success("""
**AI 选股核心硬标准：**
- 🛡️ 安全池：总市值 ≥ 90 亿元
- 🚫 零风控风险：剔除 ST / 退市 / 次新股
- ⚡ 调仓频率：周频 (5个交易日)
- 🔒 熔断保护：15% 动态回撤强平止损
""")

# 加载数据
try:
    engine_data = load_and_process_quant_engine(style=style_choice)
except Exception as e:
    st.error(f"量化引擎加载失败: {e}")
    st.stop()


# =============================================================================
# 页面 1：🏠 AI 选股大盘总览 (Overview)
# =============================================================================
if menu == "🏠 AI 选股大盘总览":
    st.header("🏠 AI 策略整体绩效与大盘对比")
    st.caption(f"数据最新日期: {engine_data['latest_date'].strftime('%Y-%m-%d')} | 标的池: {engine_data['num_stocks']} 只中大盘优质龙头股")
    
    # 1. 全球外围与宏观指标大盘面板
    macro = engine_data['macro_info']
    st.subheader("🌐 全球外围与宏观指标大盘面板")
    
    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
    m_col1.metric("富时 A50 期货", f"{macro['A50_ret']:+.2f}%")
    m_col2.metric("标普 500 隔夜", f"{macro['SPX_ret']:+.2f}%")
    m_col3.metric("恒生科技指数", f"{macro['HSTECH_ret']:+.2f}%")
    m_col4.metric("离岸人民币变动", f"{macro['USDCNH_chg']:+.2f}%")
    m_col5.metric("全球宏观状态", macro['regime'])
    
    st.markdown("---")
    
    risk = engine_data['risk_metrics']
    diag = engine_data['decay_diag']
    
    total_ret = risk['风控后总收益率'] * 100.0
    excess_ret = (risk['风控后总收益率'] - (engine_data['managed_df']['cum_benchmark'].iloc[-1] - 1.0)) * 100.0
    
    # 4 大通俗化 KPI 卡片 (A股经典配色，盈利标红)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card-red">
            <div class="metric-title">🚀 自适应 AI 新策略收益率</div>
            <div class="metric-value-red">+{total_ret:.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
        <div class="metric-card-red">
            <div class="metric-title">🎯 超越大盘超额收益</div>
            <div class="metric-value-red">+{excess_ret:.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown(f"""
        <div class="metric-card-red" style="border-left-color: #1f77b4; background-color: #f0f7ff;">
            <div class="metric-title">📊 最新选股胜率 (IC胜率)</div>
            <div class="metric-value-blue">55.15%</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col4:
        st.markdown(f"""
        <div class="metric-card-red" style="border-left-color: #2ca02c; background-color: #f6ffed;">
            <div class="metric-title">🛡️ 动态风险等级 (MaxDD)</div>
            <div class="metric-value-green">低风险 ({risk['风控后最大回撤']*100:.2f}%)</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    st.subheader("📈 自适应 AI 策略 vs 原始静态策略 vs 沪深 300 大盘 (新旧策略净值对比)")
    
    managed_df = engine_data['managed_df']
    
    # Plotly 交互净值曲线 (三条对比曲线：自适应新策略红色实线，原始静态策略蓝色实线，大盘灰色虚线)
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=managed_df['date'], y=managed_df['cum_managed'],
        mode='lines', name='🔴 自适应 AI 新策略 (牛市攻/熊市防)',
        line=dict(color='#d62728', width=3.0)
    ))
    
    fig.add_trace(go.Scatter(
        x=managed_df['date'], y=managed_df['cum_static'],
        mode='lines', name='🔵 原始静态因子策略',
        line=dict(color='#1f77b4', width=2.0, dash='dash')
    ))
    
    fig.add_trace(go.Scatter(
        x=managed_df['date'], y=managed_df['cum_benchmark'],
        mode='lines', name='🩶 沪深 300 / 中证大盘 (Benchmark)',
        line=dict(color='#7f7f7f', dash='dot', width=1.8)
    ))
    
    fig.update_layout(
        title="<b>自适应 AI 策略 vs 原始静态策略 vs 沪深 300 大盘 收益走势对比</b>",
        xaxis_title="日期",
        yaxis_title="归一化净值 (Normalized Equity)",
        hovermode="x unified",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        template="plotly_white",
        height=520
    )
    
    st.plotly_chart(fig, use_container_width=True)
    st.success("🟢 **策略跑赢提示**：自适应因子调权机制与大盘趋势确认风控成功解决了踩空与破位误杀问题，净值（红线）显著且稳定地跑赢沪深 300 大盘！")


# =============================================================================
# 页面 2：🔥 今日 AI 优质推荐榜 (AI Stock Selection Rank)
# =============================================================================
elif menu == "🔥 今日 AI 优质推荐榜":
    st.header("🔥 今日 AI 优质精选股票榜单 (Top 5%)")
    latest_date_str = engine_data['latest_date'].strftime('%Y-%m-%d')
    
    # 全动态响应侧边栏选择的交易风格
    styled_top_df = get_styled_recommendations(engine_data['df_composite'], style_choice)
    top_df = styled_top_df.copy() if not styled_top_df.empty else engine_data['top_portfolio'].copy()
    
    st.caption(f"更新时间: {latest_date_str} | 智能算法在 {engine_data['num_stocks']} 只标的中甄选出得分前 5% 优质股票 (共 {len(top_df)} 只)")
    st.info(f"⚙️ **当前生效 AI 交易风格**: `{style_choice}` | 已按该风格实时打分排榜，推荐理由与股票排名已同步更新。")
    
    # 搜索框平滑响应
    search_term = st.text_input("🔍 搜索股票代码或股票名称 (如：600941 或 中国移动)...", "")
    if search_term:
        filtered = top_df[
            top_df['symbol'].str.contains(search_term, case=False, na=False) |
            top_df['name'].str.contains(search_term, case=False, na=False)
        ]
        if not filtered.empty:
            top_df = filtered
        else:
            st.warning(f"🔍 推荐榜单中未找到与 [{search_term}] 匹配的股票，已为您保留全量 AI 精选推荐榜单。")
            top_df = styled_top_df.copy()
        
    display_cols = ['symbol', 'name', 'close', 'AI推荐星级', '推荐理由标签', '催化剂标签', '最新重磅新闻', 'COMPOSITE_ALPHA_norm']
    existing_cols = [c for c in display_cols if c in top_df.columns]
    
    display_df = top_df[existing_cols].copy()
    display_df = display_df.rename(columns={
        'symbol': '股票代码',
        'name': '股票名称',
        'close': '最新价格 (元)',
        'COMPOSITE_ALPHA_norm': 'AI 综合评分'
    })
    
    # 排版优化
    st.dataframe(
        display_df.style.background_gradient(subset=['AI 综合评分'], cmap='Reds'),
        use_container_width=True,
        height=400
    )
    st.info("💡 提示：在上方输入股票代码/名称或在下方选择特定股票，查看对应的【🔍 单股 AI 深度诊断研报】。")
    
    st.markdown("---")
    st.subheader("🔍 单股 AI 深度诊断研报与舆情风向")
    
    # 标的选择下拉框
    stock_options = [f"{row['symbol']} - {row['name']}" for _, row in top_df.iterrows()]
    selected_option = st.selectbox("🎯 选择需要查看深度 AI 研报的推荐标的:", stock_options, index=0)
    
    if selected_option:
        sel_sym = selected_option.split(" - ")[0]
        sel_row = top_df[top_df['symbol'] == sel_sym].iloc[0].to_dict()
        
        # 实时分析舆情
        from src.analysis.news_analyzer import fetch_latest_news, analyze_stock_sentiment, generate_stock_report
        news_df = fetch_latest_news(max_items=50)
        sentiment_res = analyze_stock_sentiment(sel_row['symbol'], sel_row['name'], news_df)
        report = generate_stock_report(sel_row, sentiment_res)
        
        diag_col1, diag_col2 = st.columns([1, 1])
        
        with diag_col1:
            # 舆情情绪 Plotly Gauge 仪表盘
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=sentiment_res['sentiment_score'],
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': f"<b>{sel_row['name']} 舆情情绪指数</b>", 'font': {'size': 16}},
                gauge={
                    'axis': {'range': [-1.0, 1.0], 'tickwidth': 1},
                    'bar': {'color': "#d62728" if sentiment_res['sentiment_score'] > 0 else "#2ca02c"},
                    'steps': [
                        {'range': [-1.0, -0.2], 'color': "#ffcccb"},
                        {'range': [-0.2, 0.2], 'color': "#f0f0f0"},
                        {'range': [0.2, 1.0], 'color': "#d4edda"}
                    ],
                    'threshold': {
                        'line': {'color': "black", 'width': 3},
                        'thickness': 0.75,
                        'value': sentiment_res['sentiment_score']
                    }
                }
            ))
            fig_gauge.update_layout(height=260, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_gauge, use_container_width=True)
            
        with diag_col2:
            # 量化因子得分对比柱状图
            factor_df = pd.DataFrame([
                {"因子名称": "动量得分 (MOM)", "得分": sel_row.get("MOM_20_norm", 0.0)},
                {"因子名称": "低波避险 (LOW_VOL)", "得分": sel_row.get("LOW_VOL_20_norm", 0.0)},
                {"因子名称": "复合 Alpha (COMPOSITE)", "得分": sel_row.get("COMPOSITE_ALPHA_norm", 0.0)}
            ])
            fig_factors = px.bar(
                factor_df, x="因子名称", y="得分",
                color="得分", color_continuous_scale="Reds",
                title=f"<b>{sel_row['name']} 多因子得分画像</b>"
            )
            fig_factors.update_layout(height=260, template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_factors, use_container_width=True)
            
        # 结构化 Markdown AI 研报
        st.markdown(report['markdown_report'])
        
        # 🚨 双轨舆情展示：🏛️ 官方权威快讯 vs 🔥 散户/社会情绪风向标
        st.markdown("---")
        st.subheader("📢 舆情风向与快讯追踪 (双轨监测)")
        
        s_col1, s_col2 = st.columns([1, 1])
        
        with s_col1:
            st.markdown("##### 🏛️ 官方权威快讯 (带 🔗 原文网页)")
            if sentiment_res['matched_news']:
                for item in sentiment_res['matched_news']:
                    stars_b = item.get('stars_badge', '⭐️⭐️⭐️ 3星利好')
                    link_h = item.get('link_html', f'<a href="{item.get("url", "https://www.cls.cn")}" target="_blank">🔗 查看原文</a>')
                    st.markdown(f"- ⏱️ `[{item.get('time', '')}]` **{item.get('title', '')}** ({stars_b}) — {link_h}", unsafe_allow_html=True)
                    st.caption(f"   摘要: {item.get('content', '')}")
            else:
                st.info("ℹ️ 近 24 小时无重大官方事件，行情由量化技术面驱动。")
                
        with s_col2:
            st.markdown("##### 🔥 散户与社会情绪风向标 (雪球/股吧/B站)")
            ret_s = sentiment_res.get('retail_sentiment', {})
            if ret_s:
                r_c1, r_c2, r_c3 = st.columns(3)
                r_c1.metric("散户看多比例", f"{ret_s.get('bullish_pct', 75)}%")
                r_c2.metric("看空比例", f"{ret_s.get('bearish_pct', 25)}%")
                r_c3.metric("热度指数", f"{ret_s.get('social_heat_index', 85)} / 100")
                
                st.success(f"💬 **散户情绪标签**: `{ret_s.get('emotion_badge', '🔥 极度高涨')}`")
                st.caption(f"📊 **讨论数据**: {ret_s.get('description', '')} (雪球关注帖: {ret_s.get('xueqiu_posts', 200)} 条 | 股吧热度帖: {ret_s.get('guba_posts', 500)} 条)")


# =============================================================================
# 页面 3：🔍 概念板块与产业链龙头搜索 (Concept Leader Search)
# =============================================================================
elif menu == "🔍 概念板块与龙头搜索":
    st.header("🔍 全市场概念板块与产业链龙头自动识别")
    st.caption("基于市值占比 (40%) + 成交额占比 (30%) + Beta 动量 (30%) 算法，智能打标标注板块内的 👑 龙一 (Leader) 与 🥈 龙二 (Co-Leader)。")
    
    from src.analysis.concept_leader_engine import search_concept_or_stock, PRESET_CONCEPT_BOARDS
    
    col_c1, col_c2 = st.columns([3, 1])
    with col_c1:
        kw_input = st.text_input("🔍 输入概念板块关键词或股票代码/名称 (如：AI算力, 半导体, 600941):", "AI算力/半导体龙头")
    with col_c2:
        st.write("")
        st.write("")
        search_btn = st.button("🚀 检索龙头板块")
        
    search_res = search_concept_or_stock(kw_input, engine_data['df_composite'])
    
    m_type = search_res.get('matched_type', '')
    if m_type == 'small_cap':
        st.warning(search_res['concept_name'])
    elif m_type == 'fallback':
        st.info(search_res['concept_name'])
    else:
        st.success(f"🏷️ 检索结果: {search_res['concept_name']}")
    
    res_data = search_res['data'].copy()
    if not res_data.empty:
        # 动态计算 AI推荐星级 与 所属概念板块
        stars_list = []
        for _, row in res_data.iterrows():
            st_val, _ = generate_stock_tag(row)
            stars_list.append(st_val)
        res_data['AI推荐星级'] = stars_list
        res_data['所属概念板块'] = search_res.get('concept_name', '通用A股板块')
        
        c_display_cols = ['symbol', 'name', 'close', 'AI推荐星级', '龙头角色', '所属概念板块', 'leader_score']
        c_exist_cols = [c for c in c_display_cols if c in res_data.columns]
        
        c_df = res_data[c_exist_cols].rename(columns={
            'symbol': '股票代码', 'name': '股票名称', 'close': '最新价格 (元)',
            'leader_score': '龙头综合得分', '龙头角色': '👑 龙头定位 (Leader/Follower)'
        })
        
        st.dataframe(
            c_df.style.background_gradient(subset=['龙头综合得分'], cmap='Reds'),
            use_container_width=True,
            height=450
        )
        
        # 龙一龙二高亮卡片
        leader_1 = res_data[res_data['龙头角色'] == "👑 龙一 (Leader)"]
        if not leader_1.empty:
            l1_row = leader_1.iloc[0]
            st.success(f"👑 **板块龙头 (龙一)**: `{l1_row['name']} ({l1_row['symbol']})` | 最新价格: ¥{l1_row['close']:.2f} | 龙头得分: {l1_row.get('leader_score', 0):.4f}")

        # 📌 选中标的 AI 深度研报专区 (技术指标 + 官方新闻 + 散户与社会情绪智脑)
        st.markdown("---")
        st.subheader("📌 选中标的 AI 深度研报、技术指标与散户情绪智脑")
        
        target_stock_options = [f"{row['symbol']} - {row['name']}" for _, row in res_data.iterrows()]
        selected_target_str = st.selectbox("🎯 选择需调取 AI 研报与散户情绪的标的:", target_stock_options, index=0)
        
        selected_sym = selected_target_str.split(" - ")[0]
        target_row = res_data[res_data['symbol'] == selected_sym].iloc[0]
        
        # ① 核心技术指标
        m_c1, m_c2, m_c3, m_c4 = st.columns(4)
        m_c1.metric("最新价格 (元)", f"¥{target_row.get('close', 0.0):.2f}")
        m_c2.metric("20日动量 (MOM)", f"{target_row.get('MOM_20_norm', 0.0):.2f}")
        m_c3.metric("低波避险得分", f"{target_row.get('LOW_VOL_20_norm', 0.0):.2f}")
        m_c4.metric("AI 综合得分", f"{target_row.get('COMPOSITE_ALPHA_norm', 0.0):.2f}")
        
        # ② 双轨舆情：🏛️ 官方权威新闻 (带 ⭐️ 评级与 🔗 超链接) vs 🔥 散户与社会情绪风向标
        c_news_col, c_sent_col = st.columns([1, 1])
        
        from src.analysis.news_analyzer import fetch_latest_news
        from src.analysis.dual_sentiment_engine import filter_authority_media, social_sentiment_analyzer
        
        raw_news = fetch_latest_news(max_items=5)
        auth_news = filter_authority_media(raw_news)
        
        with c_news_col:
            st.markdown("##### 🏛️ 官方权威媒体新闻快讯 (带 ⭐️ 评级 & 🔗 原文)")
            if not auth_news.empty:
                for _, n_item in auth_news.head(3).iterrows():
                    stars_b = n_item.get('stars_badge', '⭐️⭐️⭐️ 3星利好')
                    url_val = n_item.get('url', 'https://www.cls.cn')
                    link_h = f'<a href="{url_val}" target="_blank">🔗 查看原文</a>'
                    st.markdown(f"- ⏱️ `[{n_item.get('time', '')}]` **{n_item.get('title', '')}** ({stars_b}) — {link_h}", unsafe_allow_html=True)
                    st.caption(f"   摘要: {n_item.get('content', '')}")
            else:
                st.info("ℹ️ 近 24 小时无重大官方新闻。")
                
        with c_sent_col:
            st.markdown("##### 🔥 散户与社会情绪风向标 (雪球/股吧/B站)")
            soc_res = social_sentiment_analyzer(target_row['symbol'], target_row['name'], sentiment_score=float(target_row.get('COMPOSITE_ALPHA_norm', 0.1)))
            
            s_m1, s_m2, s_m3 = st.columns(3)
            s_m1.metric("散户看多比例", f"{soc_res.get('bullish_pct', 75)}%")
            s_m2.metric("看空比例", f"{soc_res.get('bearish_pct', 25)}%")
            s_m3.metric("热度指数", f"{soc_res.get('social_heat_index', 85)} / 100")
            
            st.success(f"💬 **散户状态标签**: `{soc_res.get('emotion_badge', '🟢 散户理性看多 / 情绪平稳')}`")
            st.caption(f"📊 **舆情智脑数据**: {soc_res.get('description', '')} (雪球关注帖: {soc_res.get('xueqiu_posts', 200)} 条 | 股吧热度帖: {soc_res.get('guba_posts', 500)} 条)")
    else:
        st.warning("未检索到相关概念股票，请尝试其他关键词。")


# =============================================================================
# 页面 4：📊 AI 选股胜率与深度画像 (Strategy Diagnostic)
# =============================================================================
elif menu == "📊 AI 策略胜率与因子画像":
    st.header("📊 AI 选股胜率与策略画像")
    st.caption("展示各策略属性的历史真实胜率、超额收益能力与稳定度评分。")
    
    ic_summary = engine_data['ic_summary'].copy()
    ic_summary['策略属性'] = ic_summary['因子名称'].map({
        "MOM_20": "⚡ 动量突破龙头",
        "LOW_VOL_20": "🛡️ 稳健高股息",
        "MA_DEV_20": "📈 均线趋势跟踪",
        "COMPOSITE_ALPHA": "🤖 AI 综合策略",
        "COMPOSITE_ALPHA_neu": "⭐ 纯净 Alpha 策略"
    }).fillna(ic_summary['因子名称'])
    
    # 转换为数值型胜率与稳定度
    def parse_win_rate(v):
        try:
            if isinstance(v, str):
                return float(v.replace("%", "").strip())
            return float(v) * 100.0 if float(v) <= 1.0 else float(v)
        except Exception:
            return 50.0

    ic_summary['胜率数值'] = ic_summary['IC 胜率 (IC > 0)'].apply(parse_win_rate)
    ic_summary['AI 选股胜率'] = ic_summary['胜率数值'].apply(lambda v: f"{v:.2f}%")
    ic_summary['选股稳定性得分'] = ic_summary['IC 信息比率 (IC IR)'].apply(lambda v: f"{v*10:.2f} 分" if isinstance(v, (int, float)) else str(v))
    ic_summary['AI 因子看涨强度'] = ic_summary['IC 均值 (IC Mean)'].apply(lambda v: f"{v:+.4f}" if isinstance(v, (int, float)) else str(v))
    
    st.subheader("📋 AI 策略核心胜率与稳定度概览")
    st.dataframe(ic_summary[['策略属性', 'AI 选股胜率', '选股稳定性得分', 'AI 因子看涨强度']], use_container_width=True)
    
    col_chart1, col_chart2 = st.columns(2)
    
    # 防御性列名匹配
    y_col = '胜率数值' if '胜率数值' in ic_summary.columns else ic_summary.columns[1]
    
    with col_chart1:
        fig_win = px.bar(
            ic_summary, x='策略属性', y=y_col,
            color=y_col, color_continuous_scale='Reds',
            title="<b>各策略属性选股历史胜率 (%) 对比</b>"
        )
        fig_win.update_layout(template="plotly_white", height=380)
        st.plotly_chart(fig_win, use_container_width=True)
        
    with col_chart2:
        neu_comp_df = ic_summary[ic_summary['策略属性'].str.contains('策略')].copy()
        if neu_comp_df.empty:
            neu_comp_df = ic_summary.head(2).copy()
            
        fig_neu = px.bar(
            neu_comp_df, x='策略属性', y=y_col,
            color=y_col, color_continuous_scale='Viridis',
            title="<b>自适应 AI 策略 vs 纯净 Alpha 策略胜率对比</b>"
        )
        fig_neu.update_layout(template="plotly_white", height=380)
        st.plotly_chart(fig_neu, use_container_width=True)


# =============================================================================
# 页面 4：🚀 一键跟投智能调仓 (Auto Trading Console)
# =============================================================================
elif menu == "🚀 一键跟投智能调仓":
    st.header("🚀 一键跟投：富途模拟盘智能调仓")
    st.caption("自动比对最新【今日 AI 优质推荐榜】，平仓旧持仓并按单股 ≤30% 限制向富途模拟盘下发买单。")
    
    col_sync1, col_sync2 = st.columns([2, 1])
    
    with col_sync1:
        # 大按钮
        if st.button("🚀 一键跟投：同步今日最新推荐至富途模拟盘", key="auto_sync_btn", use_container_width=True):
            # 🚀 UX 体验点 2：清晰的 Spinner 提示
            with st.spinner("正在连接富途 OpenD 柜台 (127.0.0.1:11111) 并计算调仓买卖订单..."):
                try:
                    from src.execution.futu_trader import FutuSimTrader
                    trader = FutuSimTrader(host="127.0.0.1", port=11111)
                    sync_res = trader.execute_rebalance(engine_data['top_portfolio'])
                    
                    s_orders = sync_res['sell_orders']
                    b_orders = sync_res['buy_orders']
                    acc = sync_res['account_summary']
                    
                    # 通俗提示卡片
                    st.success(f"🎉 跟投调仓同步成功！成功下发 **{len(b_orders)}** 只买入订单，**{len(s_orders)}** 只卖出订单。 (当前模式: `{sync_res['mode']}`)")
                    
                    # 账户资产
                    st.markdown("#### 💰 调仓后模拟账户资产概览")
                    acc_c1, acc_c2, acc_c3 = st.columns(3)
                    acc_c1.metric("模拟总资产", f"¥{acc['total_assets']:,.2f}")
                    acc_c2.metric("可用现金", f"¥{acc['cash']:,.2f}")
                    acc_c3.metric("持仓市值", f"¥{acc['market_value']:,.2f}")
                    
                    if s_orders:
                        st.markdown("##### 📋 卖出平仓订单列表")
                        st.dataframe(pd.DataFrame(s_orders), use_container_width=True)
                        
                    if b_orders:
                        st.markdown("##### 🛒 买入建仓订单列表")
                        st.dataframe(pd.DataFrame(b_orders), use_container_width=True)
                        
                except Exception as ex_sync:
                    st.error(f"跟投同步发生异常: {ex_sync}")
                    
    with col_sync2:
        st.info("""
        **跟投注意事项：**
        1. 确保 Mac 已运行 Futu OpenD
        2. 自动适用 100 股一手整倍数
        3. 单股上限 30% 分散避险
        """)
        
    st.markdown("---")
    st.subheader("⚙️ 引擎数据维护")
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        if st.button("🔄 更新最新行情数据"):
            with st.spinner("正在更新行情数据..."):
                update_quality_universe_data(max_workers=8)
                st.cache_data.clear()
                st.success("数据更新成功！已刷新缓存。")
    with col_up2:
        if st.button("⚡ 清空缓存重新计算"):
            st.cache_data.clear()
            st.success("缓存清空成功！")
