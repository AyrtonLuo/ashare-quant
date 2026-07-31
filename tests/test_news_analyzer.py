"""
test_news_analyzer.py
测试全球新闻抓取、Sentiment 舆情打分与防御性降级机制
"""

import pytest
import pandas as pd
from src.analysis.news_analyzer import fetch_latest_news, analyze_stock_sentiment, generate_stock_report


def test_fetch_latest_news():
    """测试抓取全球/财经快讯接口"""
    news_df = fetch_latest_news(max_items=10)
    assert not news_df.empty
    assert "title" in news_df.columns
    assert "content" in news_df.columns


def test_sentiment_defensive_fallback():
    """测试个股无新闻时的【防御性降级机制】(赋予 0.0 中性分，不引发异常)"""
    mock_news = pd.DataFrame([
        {"full_text": "美联储维持利率不变，美股纳斯达克指数震荡上涨。"}
    ])
    
    # 针对冷门股票搜索 (无匹配新闻)
    res = analyze_stock_sentiment("600999", "冷门不匹配股票", mock_news)
    
    assert res["sentiment_score"] == 0.0
    assert res["sentiment_label"] == "🟡 中性平稳"
    assert "技术面驱动" in res["summary_msg"]
    assert len(res["matched_news"]) == 0


def test_generate_stock_report():
    """测试生成结构化 AI 诊断研报"""
    mock_news = pd.DataFrame([
        {"title": "盐田港吞吐量大增，机构强烈推荐买入", "full_text": "盐田港吞吐量大增，机构强烈推荐买入，业绩突破。"}
    ])
    
    s_res = analyze_stock_sentiment("000088", "盐田港", mock_news)
    assert s_res["sentiment_score"] > 0.0
    
    stock_row = {
        "symbol": "000088",
        "name": "盐田港",
        "close": 4.48,
        "COMPOSITE_ALPHA_norm": 1.45,
        "MOM_20_norm": 0.70,
        "LOW_VOL_20_norm": 1.45,
        "AI推荐星级": "⭐⭐⭐⭐⭐",
        "推荐理由标签": "🔥 攻守兼备 / 机构重仓"
    }
    
    report = generate_stock_report(stock_row, s_res)
    assert "markdown_report" in report
    assert "盐田港" in report["markdown_report"]
    assert "核心看涨逻辑" in report["markdown_report"]
