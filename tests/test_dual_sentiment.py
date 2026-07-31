"""
test_dual_sentiment.py
测试官方权威媒体白名单限制与散户/社会情绪双轨吸收智脑
"""

import pytest
import pandas as pd
from src.analysis.dual_sentiment_engine import filter_authority_media, fetch_social_sentiment


def test_filter_authority_media():
    """测试权威媒体白名单过滤功能"""
    mock_df = pd.DataFrame([
        {"title": "财联社重磅快讯", "source": "财联社"},
        {"title": "新浪财经独家研报", "source": "新浪财经"},
        {"title": "小道自媒体传言", "source": "某八卦炒股论坛"}
    ])
    
    filtered = filter_authority_media(mock_df)
    assert not filtered.empty
    sources = filtered["source"].tolist()
    assert "财联社" in sources
    assert "某八卦炒股论坛" not in sources


def test_fetch_social_sentiment():
    """测试散户与社会情绪抓取与指数计算"""
    res = fetch_social_sentiment("600941", "中国移动", sentiment_score=0.5)
    assert "social_heat_index" in res
    assert "bullish_pct" in res
    assert "bearish_pct" in res
    assert "emotion_badge" in res
    assert 0 <= res["social_heat_index"] <= 100
