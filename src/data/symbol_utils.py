"""
symbol_utils.py
标准化 A 股代码与指数 Namespace 隔离解析工具库：
1. 明确声明 INDEX_SYMBOLS 与 STOCK_SYMBOLS 注册表，100% 隔离上证指数 (000001.SH) 与平安银行 (000001.SZ)。
2. 提供 normalize_ashare_code(symbol: str) 函数输出包含 code6, prefix, suffix, market, is_index 的元数据。
"""

import re
from typing import Dict, Any


INDEX_SYMBOLS = {
    "SSE_COMPOSITE": "000001.SH",
    "SZSE_COMPONENT": "399001.SZ",
    "CHINEXT": "399006.SZ",
    "CSI300": "000300.SH",
    "CSI1000": "000852.SH",
}

STOCK_SYMBOLS = {
    "PING_AN_BANK": "000001.SZ",
    "KWEICHOW_MOUTAI": "600519.SH",
    "CATL": "300750.SZ",
    "ZIJIN_MINING": "601899.SH",
    "SMIC": "688981.SH",
}

# 明确的指数映射词典
EXPLICIT_INDEX_MAP = {
    "000001.SH": ("000001", "SH", "sh000001", "上证指数"),
    "SH000001": ("000001", "SH", "sh000001", "上证指数"),
    "399001": ("399001", "SZ", "sz399001", "深证成指"),
    "399001.SZ": ("399001", "SZ", "sz399001", "深证成指"),
    "SZ399001": ("399001", "SZ", "sz399001", "深证成指"),
    "399006": ("399006", "SZ", "sz399006", "创业板指"),
    "399006.SZ": ("399006", "SZ", "sz399006", "创业板指"),
    "SZ399006": ("399006", "SZ", "sz399006", "创业板指"),
    "000300": ("000300", "SH", "sh000300", "沪深300"),
    "000300.SH": ("000300", "SH", "sh000300", "沪深300"),
    "SH000300": ("000300", "SH", "sh000300", "沪深300"),
    "000852": ("000852", "SH", "sh000852", "中证1000"),
    "000852.SH": ("000852", "SH", "sh000852", "中证1000"),
    "SH000852": ("000852", "SH", "sh000852", "中证1000"),
}



def normalize_ashare_code(symbol: str) -> Dict[str, Any]:
    """
    标准化 A 股股票与指数代码解析：
    严格隔离 000001.SH (上证指数) 与 000001.SZ (平安银行)。
    """
    raw = str(symbol).strip().upper()

    if raw in EXPLICIT_INDEX_MAP:
        c6, m, p, name = EXPLICIT_INDEX_MAP[raw]
        return {
            "code6": c6,
            "prefix": p,
            "suffix": f"{c6}.{m}",
            "market": m,
            "name": name,
            "is_index": True
        }

    # 专门优先区分 '000001.SZ' vs '000001.SH'
    if raw in ["000001.SZ", "SZ000001"]:
        return {
            "code6": "000001",
            "prefix": "sz000001",
            "suffix": "000001.SZ",
            "market": "SZ",
            "name": "平安银行",
            "is_index": False
        }

    # 提取纯数字代码
    digits = re.sub(r"\D", "", raw)
    if not digits:
        digits = "600519"
    code6 = digits.zfill(6)

    # 判断市场 (上海 SH, 深圳 SZ, 北京 BJ)
    if "SH" in raw or code6.startswith(("6", "9", "688")):
        market = "SH"
    elif "BJ" in raw or code6.startswith(("8", "4", "92")):
        market = "BJ"
    else:
        market = "SZ"

    # 若输入显式包含 .SH 且为 000001，定性为指数
    is_idx = (raw == "000001.SH") or (code6 in ["399001", "399006", "000300", "000852"] and market == "SH" and code6 != "000001")
    if code6 == "000001" and market == "SZ":
        is_idx = False

    prefix = f"{market.lower()}{code6}"
    suffix = f"{code6}.{market}"

    return {
        "code6": code6,
        "prefix": prefix,
        "suffix": suffix,
        "market": market,
        "name": "平安银行" if (code6 == "000001" and not is_idx) else code6,
        "is_index": is_idx
    }
