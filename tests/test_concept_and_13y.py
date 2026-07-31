"""
test_concept_and_13y.py
测试概念板块龙头识别算法、DuckDB 13年数据懒加载与新闻 URL ⭐️1~⭐️5重要度评分
"""

import os
import pytest
import pandas as pd
from src.analysis.concept_leader_engine import leader_stock_identifier, search_concept_or_stock
from src.analysis.news_analyzer import classify_news_importance
from src.data_updater import query_history_with_duckdb


def test_leader_stock_identifier():
    """测试产业链龙头智能识别算法 (👑 龙一 / 🥈 龙二)"""
    mock_df = pd.DataFrame([
        {"symbol": "688981", "name": "中芯国际", "date": "2026-07-31", "close": 90.0, "total_mv_yi": 5000.0, "MOM_20_norm": 1.2},
        {"symbol": "600584", "name": "长电科技", "date": "2026-07-31", "close": 35.0, "total_mv_yi": 600.0, "MOM_20_norm": 0.8},
        {"symbol": "002371", "name": "北方华创", "date": "2026-07-31", "close": 320.0, "total_mv_yi": 1500.0, "MOM_20_norm": 1.0}
    ])
    
    res = leader_stock_identifier("AI算力/半导体龙头", mock_df)
    assert not res.empty
    assert "龙头角色" in res.columns
    assert "leader_score" in res.columns
    assert res.iloc[0]["龙头角色"] == "👑 龙一 (Leader)"


def test_search_concept_or_stock():
    """测试全市场股票与概念板块搜索"""
    mock_df = pd.DataFrame([
        {"symbol": "600941", "name": "中国移动", "date": "2026-07-31", "close": 97.41, "total_mv_yi": 20000.0, "MOM_20_norm": 1.1}
    ])
    
    search_res = search_concept_or_stock("中国移动", mock_df)
    assert search_res["matched_type"] in ["stock", "concept", "fallback"]
    assert not search_res["data"].empty


def test_classify_news_importance_and_url():
    """测试新闻 ⭐️1~⭐️5 星级重要度评级与 target=_blank 网页链接"""
    title = "格力电器发布重磅分红预案，业绩大增翻倍"
    content = "高股息分红引关注，机构重仓买入。"
    url = "https://www.cls.cn/detail/12345"
    
    res = classify_news_importance(title, content, url)
    assert "5星重磅" in res["stars_badge"] or "4星重要" in res["stars_badge"]
    assert "target=\"_blank\"" in res["link_html"]
    assert res["url"] == url


def test_duckdb_lazy_scan():
    """测试 DuckDB 懒加载查询 2013+ 历史数据"""
    parquet_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "stocks_daily.parquet")
    if os.path.exists(parquet_path):
        df_duck = query_history_with_duckdb(parquet_path, start_date="2023-01-01")
        assert not df_duck.empty
        assert "symbol" in df_duck.columns
