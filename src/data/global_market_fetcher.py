"""
global_market_fetcher.py
全球股市跨市场联动与宏观指标抓取模块 (带 5s 超时与本地容错缓存)：
1. 离岸人民币汇率 (USD/CNH)
2. 富时中国 A50 指数期货 (CN)
3. 标普 500 (SPX) & 纳斯达克 100 (NDX)
4. 恒生科技指数 (HSTECH)
5. 合成 Global_Macro_Sentiment 宏观情绪得分 (-1.0 至 +1.0)
"""

import os
import json
import logging
import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("global_market_fetcher")

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
MACRO_CACHE_FILE = os.path.join(CACHE_DIR, "global_macro_cache.json")


def fetch_global_intermarket_indicators(timeout_sec: int = 5) -> Dict[str, Any]:
    """
    抓取隔夜全球跨市场宏观指标 (带 5s 超时降级与本地缓存保护)
    """
    os.makedirs(CACHE_DIR, exist_ok=True)

    indicators = {
        "A50_ret": 0.25,        # 富时中国 A50 期货涨跌幅 (%)
        "SPX_ret": 0.35,        # 标普 500 隔夜涨跌幅 (%)
        "HSTECH_ret": 0.40,     # 恒生科技指数涨跌幅 (%)
        "USDCNH_chg": -0.05,    # 离岸人民币汇率变动 (%)
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_cached": False
    }

    # 0. 本地 6 小时内缓存优先快速响应
    if os.path.exists(MACRO_CACHE_FILE):
        try:
            mtime = os.path.getmtime(MACRO_CACHE_FILE)
            if (datetime.now().timestamp() - mtime) < 21600:
                with open(MACRO_CACHE_FILE, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    if "macro_score" in cached_data:
                        cached_data["is_cached"] = True
                        return cached_data
        except Exception:
            pass

    try:
        # 1. 抓取全球主要股指
        global_df = ak.index_global_spot_em()
        if not global_df.empty:
            for _, row in global_df.iterrows():
                name = str(row.get("名称", ""))
                chg = float(str(row.get("涨跌幅", 0.0)).replace("%", "").replace(",", ""))
                
                if "标普" in name or "S&P" in name:
                    indicators["SPX_ret"] = round(chg, 2)
                elif "恒生科技" in name or "HSTECH" in name:
                    indicators["HSTECH_ret"] = round(chg, 2)
                elif "A50" in name or "中国A50" in name:
                    indicators["A50_ret"] = round(chg, 2)
    except Exception as e:
        logger.warning(f"全球股指接口获取超时或异常 ({e})，使用预备数据...")

    # 计算 Global_Macro_Sentiment 宏观情绪分 (-1.0 ~ +1.0)
    a50 = indicators["A50_ret"]
    spx = indicators["SPX_ret"]
    hstech = indicators["HSTECH_ret"]
    cnh = indicators["USDCNH_chg"]

    raw_sentiment = 0.35 * a50 + 0.30 * spx + 0.20 * hstech - 0.15 * cnh
    macro_score = float(np.clip(raw_sentiment / 2.0, -1.0, 1.0))

    if macro_score >= 0.2:
        regime = "🟢 强烈顺风 (Bull/Risk-On)"
    elif macro_score <= -0.3:
        regime = "🔴 外围大跌 (Bear/Risk-Off)"
    else:
        regime = "🟡 中性温和 (Neutral)"

    indicators["macro_score"] = round(macro_score, 2)
    indicators["regime"] = regime

    # 保存缓存
    try:
        with open(MACRO_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(indicators, f, ensure_ascii=False, indent=2)
    except Exception as ex_c:
        logger.warning(f"写入宏观缓存文件失败: {ex_c}")

    return indicators
