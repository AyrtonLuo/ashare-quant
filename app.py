"""
app.py
ashare-quant 量化研究系统 Web 控制台 (Streamlit + Plotly 版)
功能模块：
1. 🏠 首页概览：系统健康度卡片 + Plotly 动态风控净值曲线
2. 🎯 最新调仓选股名单：Top 39 优质选股交互式表格 (支持搜索与排序)
3. 🔬 因子 IC 诊断实验室：因子 IC IR/胜率对比柱状图 + 60日 Rolling IC 折线图
4. ⚙️ 数据与回测控制台：一键增量数据更新与全流程回测 (支持 st.cache_data.clear() 自动刷新)
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
from src.factor_analyzer import summarize_factor_ic, calculate_rank_ic, run_layered_backtest
from src.risk_manager import apply_risk_managed_backtest
from src.strategy_decay_analyzer import diagnose_alpha_decay

DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "data")
DAILY_PARQUET = os.path.join(DATA_DIR, "stocks_daily.parquet")

# 页面基础配置
st.set_page_config(
    page_title="ashare-quant 量化研究系统控制台",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# 🚀 性能优化 1：@st.cache_data 数据与计算结果高效缓存
# =============================================================================
@st.cache_data(show_spinner="正在拉取并计算 90亿+ 标的池多因子数据...")
def load_and_process_quant_engine():
    """读取本地 Parquet 数据，并运行多因子计算、IC 诊断与风控回测"""
    if not os.path.exists(DAILY_PARQUET):
        # 若无本地文件，先抓取更新
        update_quality_universe_data(max_workers=8)
        
    raw_df = pd.read_parquet(DAILY_PARQUET)
    raw_df['date'] = pd.to_datetime(raw_df['date'])
    
    num_stocks = raw_df['symbol'].nunique()
    
    # 计算因子
    df_factors = calculate_raw_factors(raw_df)
    df_factors['LOW_VOL_20'] = -df_factors['VOL_20']
    factor_base_names = ["MOM_20", "VOL_20", "LOW_VOL_20", "MA_DEV_20"]
    df_processed = preprocess_factors_cross_section(df_factors, factor_base_names)
    
    # 动态 IC-IR 合成 Alpha
    df_composite = build_composite_alpha_factor(df_processed, method="dynamic_ic_ir")
    
    # IC 总结
    all_factor_cols = ["MOM_20", "LOW_VOL_20", "MA_DEV_20", "COMPOSITE_ALPHA"]
    ic_summary = summarize_factor_ic(df_composite, all_factor_cols)
    
    # Top 5% 周频回测与 15% MaxDD 风控熔断
    res_df, raw_metrics = run_layered_backtest(df_composite, "COMPOSITE_ALPHA_norm", rebalance_freq=5, top_pct=0.05)
    managed_df, risk_metrics = apply_risk_managed_backtest(res_df, max_dd_limit=0.15, cooldown_days=10, max_stock_weight=0.30)
    
    # Alpha 衰减诊断与 60 日 Rolling IC
    comp_ic_df = calculate_rank_ic(df_composite, "COMPOSITE_ALPHA_norm")
    comp_ic_df['rolling_ic_60'] = comp_ic_df['rank_ic'].rolling(window=60, min_periods=20).mean()
    decay_diag = diagnose_alpha_decay(comp_ic_df, "COMPOSITE_ALPHA")
    
    # 最新调仓日选股名单
    latest_date = df_composite['date'].max()
    latest_day_data = df_composite[df_composite['date'] == latest_date].dropna(subset=['COMPOSITE_ALPHA_norm'])
    top_5pct_k = max(1, int(len(latest_day_data) * 0.05))
    top_portfolio = latest_day_data.sort_values('COMPOSITE_ALPHA_norm', ascending=False).head(top_5pct_k).copy()
    
    return {
        "num_stocks": num_stocks,
        "latest_date": latest_date,
        "df_composite": df_composite,
        "ic_summary": ic_summary,
        "managed_df": managed_df,
        "risk_metrics": risk_metrics,
        "comp_ic_df": comp_ic_df,
        "decay_diag": decay_diag,
        "top_portfolio": top_portfolio
    }


# =============================================================================
# 🎨 侧边栏导航与系统状态
# =============================================================================
st.sidebar.title("📈 ashare-quant 控制台")
st.sidebar.caption("中大盘优质标的池多因子量化研究系统")

menu = st.sidebar.radio(
    "系统导航菜单",
    ["🏠 首页概览", "🎯 最新调仓选股名单", "🔬 因子 IC 诊断实验室", "⚙️ 数据与回测控制台"],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.info("""
**系统配置硬指标：**
- 选股标的池：中大盘龙头 (799只)
- 市值门槛：总市值 ≥ 90 亿元
- 风险隔离：剔除 ST / 退市 / 次新股
- 调仓周期：周频 (5个交易日)
- 风控逻辑：15% 动态回撤强平冷静
""")


# 尝试加载缓存数据
try:
    engine_data = load_and_process_quant_engine()
except Exception as e:
    st.error(f"加载量化数据发生异常: {e}")
    st.stop()

# =============================================================================
# 页面 1：🏠 首页概览 (Overview)
# =============================================================================
if menu == "🏠 首页概览":
    st.header("🏠 系统总体运行概览")
    st.caption(f"数据集最新交易日: {engine_data['latest_date'].strftime('%Y-%m-%d')} | 标的池包含 {engine_data['num_stocks']} 只中大盘龙头股票")
    
    # 5 大 KPI 状态卡片
    col1, col2, col3, col4, col5 = st.columns(5)
    
    diag = engine_data['decay_diag']
    risk = engine_data['risk_metrics']
    
    status_label = "🟢 健康 (HEALTHY)" if not diag['is_decayed'] else "🔴 衰减 (DECAYED)"
    col1.metric("系统健康度", status_label)
    col2.metric("60日 Rolling IC", f"{diag['rolling_ic_60']:.4f}")
    col3.metric("优质股票池规模", f"{engine_data['num_stocks']} 只")
    col4.metric("组合夏普比率", f"{risk['风控后夏普比率']:.2f}")
    col5.metric("组合最大回撤", f"{risk['风控后最大回撤']*100:.2f}%")
    
    st.markdown("---")
    st.subheader("📈 组合风控熔断前后的动态净值走势对比")
    
    managed_df = engine_data['managed_df']
    
    # 绘制 Plotly 交互净值曲线
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=managed_df['date'], y=managed_df['cum_top'],
        mode='lines', name='原始 Top 5% 策略 (无风控)',
        line=dict(color='#1f77b4', dash='dash', width=1.5),
        opacity=0.7
    ))
    
    fig.add_trace(go.Scatter(
        x=managed_df['date'], y=managed_df['cum_managed'],
        mode='lines', name='风控熔断策略 (15% MaxDD & 30% 限仓)',
        line=dict(color='#d62728', width=2.5)
    ))
    
    fig.add_trace(go.Scatter(
        x=managed_df['date'], y=managed_df['cum_benchmark'],
        mode='lines', name='全集等权基准 (Benchmark)',
        line=dict(color='#7f7f7f', dash='dot', width=1.5)
    ))
    
    fig.update_layout(
        title="<b>90亿+ 中大盘优质池 动态净值对比图</b>",
        xaxis_title="日期",
        yaxis_title="归一化净值 (Normalized Equity)",
        hovermode="x unified",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        template="plotly_white",
        height=520
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 提示与建议报告
    st.success(f"**实盘部署建议**：{diag['warning_msg']}，90亿+ 标的池具备极佳的流动性与容量承载能力。")


# =============================================================================
# 页面 2：🎯 最新调仓选股名单 (Latest Portfolio Selection)
# =============================================================================
elif menu == "🎯 最新调仓选股名单":
    st.header("🎯 最新调仓日 Top 5% 优质组合选股清单")
    latest_date_str = engine_data['latest_date'].strftime('%Y-%m-%d')
    top_df = engine_data['top_portfolio'].copy()
    
    st.caption(f"最新调仓日期: {latest_date_str} | 在 {engine_data['num_stocks']} 只标的池中精选前 5% 得分最高股票 (共 {len(top_df)} 只)")
    
    # 搜索框与过滤器
    search_term = st.text_input("🔍 搜索股票代码或股票名称...", "")
    if search_term:
        top_df = top_df[
            top_df['symbol'].str.contains(search_term, case=False, na=False) |
            top_df['name'].str.contains(search_term, case=False, na=False)
        ]
        
    display_df = top_df[['symbol', 'name', 'close', 'COMPOSITE_ALPHA_norm', 'MOM_20_norm', 'LOW_VOL_20_norm']].copy()
    display_df = display_df.rename(columns={
        'symbol': '股票代码',
        'name': '股票名称',
        'close': '最新收盘价 (元)',
        'COMPOSITE_ALPHA_norm': '复合 Alpha 得分',
        'MOM_20_norm': '动量因子得分',
        'LOW_VOL_20_norm': '低波动因子得分'
    })
    
    st.dataframe(
        display_df.style.background_gradient(subset=['复合 Alpha 得分'], cmap='Greens'),
        use_container_width=True,
        height=550
    )
    st.info("💡 提示：点击任意列标题即可对选股结果按该字段进行升序或降序排列。")


# =============================================================================
# 页面 3：🔬 因子 IC 诊断实验室 (Factor IC Laboratory)
# =============================================================================
elif menu == "🔬 因子 IC 诊断实验室":
    st.header("🔬 多因子 IC 诊断与预测力实验室")
    
    ic_summary = engine_data['ic_summary']
    st.subheader("📊 因子 IC 统计指标全景对比")
    
    st.dataframe(ic_summary, use_container_width=True)
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        # IC IR 对比柱状图
        fig_ir = px.bar(
            ic_summary, x='因子名称', y='IC 信息比率 (IC IR)',
            color='IC 信息比率 (IC IR)', color_continuous_scale='Viridis',
            title="<b>各因子 IC 信息比率 (IC IR) 对比</b>"
        )
        fig_ir.update_layout(template="plotly_white", height=380)
        st.plotly_chart(fig_ir, use_container_width=True)
        
    with col_chart2:
        # IC 胜率对比柱状图
        ic_summary['IC 胜率数值'] = ic_summary['IC 胜率 (IC > 0)'].str.replace('%', '').astype(float)
        fig_win = px.bar(
            ic_summary, x='因子名称', y='IC 胜率数值',
            color='IC 胜率数值', color_continuous_scale='Plasma',
            title="<b>各因子 IC 胜率 (%) 对比</b>"
        )
        fig_win.update_layout(template="plotly_white", height=380)
        st.plotly_chart(fig_win, use_container_width=True)
        
    st.markdown("---")
    st.subheader("📉 复合 Alpha 因子 60日 Rolling IC 移动跟踪")
    
    comp_ic_df = engine_data['comp_ic_df']
    
    fig_rolling = go.Figure()
    fig_rolling.add_trace(go.Scatter(
        x=comp_ic_df['date'], y=comp_ic_df['rank_ic'],
        mode='lines', name='日度 Rank IC', line=dict(color='lightgray', width=1), opacity=0.6
    ))
    fig_rolling.add_trace(go.Scatter(
        x=comp_ic_df['date'], y=comp_ic_df['rolling_ic_60'],
        mode='lines', name='60日 Rolling IC 均值', line=dict(color='#2ca02c', width=2.5)
    ))
    fig_rolling.add_hline(y=0.0, line_dash="dash", line_color="red", annotation_text="IC 衰减熔断线 (0.0)")
    
    fig_rolling.update_layout(
        title="<b>COMPOSITE_ALPHA 60日 Rolling IC 移动追踪曲线</b>",
        xaxis_title="日期", yaxis_title="Rank IC",
        hovermode="x unified", template="plotly_white", height=420
    )
    st.plotly_chart(fig_rolling, use_container_width=True)


# =============================================================================
# 页面 4：⚙️ 数据与回测控制台 (Control Center)
# =============================================================================
elif menu == "⚙️ 数据与回测控制台":
    st.header("⚙️ 数据管道与量化引擎控制台")
    st.caption("在控制台可进行数据的实时增量更新或重新运行量化研报计算。")
    
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        st.subheader("🔄 增量数据更新")
        st.write("调用 ThreadPoolExecutor 并发抓取 90亿+ 标的池最新的日线行情数据。")
        if st.button("🚀 开始一键增量更新行情数据", key="update_btn"):
            with st.spinner("正在并发抓取与增量更新数据，请稍候..."):
                try:
                    update_quality_universe_data(max_workers=8)
                    # =========================================================
                    # 🚀 性能优化 2：刷新 Streamlit 缓存
                    # =========================================================
                    st.cache_data.clear()
                    st.success("🎉 数据增量更新成功！已自动清空缓存并刷新最新行情。")
                except Exception as ex:
                    st.error(f"更新数据失败: {ex}")
                    
    with col_btn2:
        st.subheader("⚡ 重新运行回测研报")
        st.write("重新计算全因子 IC 诊断、周频 Top 5% 分层回测与 15% MaxDD 熔断保护。")
        if st.button("📊 重新计算量化研报", key="recalc_btn"):
            with st.spinner("正在重新计算全量因子与风控净值..."):
                try:
                    st.cache_data.clear()
                    st.success("🎉 量化研报重新计算完毕！已清空旧缓存并呈现最新计算结果。")
                except Exception as ex:
                    st.error(f"重新计算失败: {ex}")
                    
    st.markdown("---")
    st.subheader("📁 本地存储文件状态")
    if os.path.exists(DAILY_PARQUET):
        file_size_mb = os.path.getsize(DAILY_PARQUET) / (1024 * 1024)
        st.success(f"• 汇总行情文件: `{DAILY_PARQUET}` (大小: {file_size_mb:.2f} MB)")
    else:
        st.warning("• 汇总行情文件尚未创建，请点击上面的更新按钮进行抓取。")
