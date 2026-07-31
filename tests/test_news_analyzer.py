"""
test_news_analyzer.py
测试全球新闻抓取、全池舆情 Alpha 融合、重大催化提取与防御性降级机制
"""

import pytest
import pandas as pd
from src.analysis.news_analyzer import (
    fetch_latest_news,
    extract_important_news,
    analyze_stock_sentiment,
    integrate_sentiment_alpha,
    generate_stock_report
)


def test_fetch_latest_news():
    """测试抓取全球/财经快讯接口"""
    news_df = fetch_latest_news(max_items=10)
    assert not news_df.empty
    assert "title" in news_df.columns
    assert "content" in news_df.columns


def test_extract_important_news():
    """测试重大重要新闻提取器 (筛选业绩大增、战略合作等催化)"""
    mock_news = pd.DataFrame([
        {"title": "中国移动与盐田港签署战略合作协议", "full_text": "中国移动与盐田港签署战略合作协议，业绩大增破百亿。"},
        {"title": "普通无催化快讯", "full_text": "今天大盘微涨 0.1%，市场表现温和。"}
    ])
    
    important = extract_important_news(mock_news)
    assert not important.empty
    assert "impact_score" in important.columns
    assert important.iloc[0]["impact_score"] > 0


def test_integrate_sentiment_alpha():
    """测试全量股票池舆情 Alpha 融合功能"""
    mock_df = pd.DataFrame([
        {"symbol": "000088", "name": "盐田港", "date": "2026-07-31", "COMPOSITE_ALPHA_neu": 1.2, "COMPOSITE_ALPHA_norm": 1.2},
        {"symbol": "600941", "name": "中国移动", "date": "2026-07-31", "COMPOSITE_ALPHA_neu": 1.1, "COMPOSITE_ALPHA_norm": 1.1}
    ])
    
    res_df = integrate_sentiment_alpha(mock_df)
    assert "SENTIMENT_ALPHA" in res_df.columns
    assert "COMPOSITE_ALPHA_final" in res_df.columns
    assert "最新重磅新闻" in res_df.columns
    assert "催化剂标签" in res_df.columns


def test_sentiment_defensive_fallback():
    """测试个股无新闻时的【防御性降级机制】(赋予 0.0 中性分，不引发异常)"""
    mock_news = pd.DataFrame([
        {"full_text": "美联储维持利率不变，美股纳斯达克指数震荡上涨。"}
    ])
    
    res = analyze_stock_sentiment("600999", "冷门不匹配股票", mock_news)
    
    assert res["sentiment_score"] == 0.0
    assert res["sentiment_label"] == "🟡 中性平稳"
    assert "技术面驱动" in res["summary_msg"]
    assert len(res["matched_news"]) == 0
