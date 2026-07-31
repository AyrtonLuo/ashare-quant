"""
auto_runner.py
无人值守每日全流程量化自动化执行管道：
1. 自动触发 90亿+ 中大盘优质标的池增量行情抓取与多线程更新
2. 运行多因子计算、市值与行业 OLS 中性化、复合 Alpha 选股
3. 抓取全球实时财经新闻与舆情 Sentiment 分析
4. 自动向富途 OpenD (TrdMarket.HK / TrdMarket.CN) 下发模拟盘智能调仓买卖订单
5. 生成每日交易与 AI 诊断简报 Markdown 文件 (以 utf-8 编码落盘保存于 data/daily_briefing_{date}.md)
"""

import os
import sys
import logging
import pandas as pd
from datetime import datetime

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

from src.data_updater import update_quality_universe_data
from src.strategy.factors import calculate_raw_factors, preprocess_factors_cross_section
from src.strategy.composite_factor import build_composite_alpha_factor
from src.strategy.factor_neutralizer import neutralize_factors_cross_section, orthogonalize_factors
from src.analysis.news_analyzer import fetch_latest_news, analyze_stock_sentiment, generate_stock_report
from src.execution.futu_trader import FutuSimTrader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("auto_runner")


def run_daily_automated_pipeline() -> str:
    """
    无人值守每日自动化量化交易与研报导出管道
    """
    logger.info("🚀 启动无人值守每日全流程量化自动化管道...")
    
    # 步骤 1: 更新行情数据
    logger.info("【1/5】更新 90 亿+ 市值标的池日线数据...")
    raw_df = update_quality_universe_data(max_workers=8, end_date="20260731")
    
    # 步骤 2: 运行 AI 选股引擎
    logger.info("【2/5】运行 AI 多因子计算、中性化与 Alpha 得分筛选...")
    df_factors = calculate_raw_factors(raw_df)
    df_factors['LOW_VOL_20'] = -df_factors['VOL_20']
    df_processed = preprocess_factors_cross_section(df_factors, ["MOM_20", "VOL_20", "LOW_VOL_20", "MA_DEV_20"])
    
    df_composite = build_composite_alpha_factor(df_processed, method="dynamic_ic_ir")
    df_composite = neutralize_factors_cross_section(df_composite, ["COMPOSITE_ALPHA"])
    df_composite = orthogonalize_factors(df_composite, ["MOM_20_norm", "LOW_VOL_20_norm", "MA_DEV_20_norm"])
    
    latest_date = df_composite['date'].max()
    date_str = latest_date.strftime("%Y-%m-%d")
    
    latest_day_data = df_composite[df_composite['date'] == latest_date].dropna(subset=['COMPOSITE_ALPHA_norm'])
    top_5pct_k = max(1, int(len(latest_day_data) * 0.05))
    top_portfolio = latest_day_data.sort_values('COMPOSITE_ALPHA_norm', ascending=False).head(top_5pct_k).copy()
    
    logger.info(f"✅ 完成 AI 选股排序，最新调仓日 ({date_str}) 选出 Top 5% 优质组合 (共 {len(top_portfolio)} 只股票)。")
    
    # 步骤 3: 抓取新闻并做 Sentiment 分析
    logger.info("【3/5】抓取全球实时财经快讯并匹配新闻舆情...")
    news_df = fetch_latest_news(max_items=50)
    
    stock_reports = []
    for _, row in top_portfolio.head(10).iterrows(): # 简报重点列出前 10 只标的
        s_res = analyze_stock_sentiment(row['symbol'], row['name'], news_df)
        report = generate_stock_report(row.to_dict(), s_res)
        stock_reports.append(report)
        
    # 步骤 4: 触发富途 OpenD 自动同步下发订单
    logger.info("【4/5】连接富途 OpenD 网关下发模拟盘智能调仓指令...")
    trader = FutuSimTrader(host="127.0.0.1", port=11111)
    futu_res = trader.execute_rebalance(top_portfolio)
    
    # 步骤 5: 导出每日简报落盘
    logger.info("【5/5】生成每日交易与 AI 诊断简报 Markdown 文件...")
    
    acc = futu_res['account_summary']
    s_orders = futu_res['sell_orders']
    b_orders = futu_res['buy_orders']
    
    briefing_md = f"""# 📈 A股/港股量化 AI 自动化每日简报 ({date_str})

## 🏆 一、 每日选股与调仓指令概览
- **标的池规模**：800 只中大盘优质股票 (总市值 ≥ 90 亿元)
- **最新选股数量**：前 5% 优选共 {len(top_portfolio)} 只标的
- **富途引擎模式**：`{futu_res['mode']}`
- **调仓后模拟总资产**：¥{acc['total_assets']:,.2f} (可用现金: ¥{acc['cash']:,.2f}, 持仓市值: ¥{acc['market_value']:,.2f})
- **成交订单概要**：成功下发 **{len(b_orders)}** 笔买入订单，**{len(s_orders)}** 笔卖出平仓订单。

---

## 🎯 二、 重点 Top 标的 AI 深度诊断简报

"""
    for rep in stock_reports:
        briefing_md += f"{rep['markdown_report']}\n"
        briefing_md += "---\n"
        
    briefing_path = os.path.join(DATA_DIR, f"daily_briefing_{date_str.replace('-', '')}.md")
    
    # =========================================================================
    # 🚨 【工程规范】：使用 utf-8 编码写入文件，确保中文显示干净
    # =========================================================================
    with open(briefing_path, "w", encoding="utf-8") as f:
        f.write(briefing_md)
        
    logger.info(f"🎉 每日简报成功生成并已保存至: {briefing_path}")
    return briefing_path


if __name__ == "__main__":
    run_daily_automated_pipeline()
