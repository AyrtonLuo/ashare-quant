"""
symbol_utils.py
标准化 A 股代码解析工具库：
提供统一的代码格式化工具函数 normalize_ashare_code(symbol: str)
自动识别并输出三种标准格式：
- code6: 纯 6 位代码 (如 '600519')
- prefix: 带有市场前缀 (如 'sh600519', 'sz000001', 'bj830549')
- suffix: 后缀格式 (如 '600519.SH', '000001.SZ', '830549.BJ')
"""

import re
from typing import Dict


def normalize_ashare_code(symbol: str) -> Dict[str, str]:
    """
    标准化 A 股股票与指数代码解析：
    支持股票 (如 '600519', '000001.SZ') 与大盘指数 ('sh000001', '000300.SH', '399001.SZ') 正确映射。
    """
    raw = str(symbol).strip().upper()

    # 专门优先处理常见大盘指数
    index_map = {
        "000001.SH": ("000001", "SH", "sh000001"),
        "SH000001": ("000001", "SH", "sh000001"),
        "000300": ("000300", "SH", "sh000300"),
        "000300.SH": ("000300", "SH", "sh000300"),
        "SH000300": ("000300", "SH", "sh000300"),
        "000852": ("000852", "SH", "sh000852"),
        "000852.SH": ("000852", "SH", "sh000852"),
        "SH000852": ("000852", "SH", "sh000852"),
        "399001": ("399001", "SZ", "sz399001"),
        "399001.SZ": ("399001", "SZ", "sz399001"),
        "SZ399001": ("399001", "SZ", "sz399001"),
        "399006": ("399006", "SZ", "sz399006"),
        "399006.SZ": ("399006", "SZ", "sz399006"),
        "SZ399006": ("399006", "SZ", "sz399006"),
    }

    if raw in index_map:
        c6, m, p = index_map[raw]
        return {"code6": c6, "prefix": p, "suffix": f"{c6}.{m}", "market": m}

    # 提取纯数字代码
    digits = re.sub(r"\D", "", raw)
    if not digits:
        digits = "600519"
    code6 = digits.zfill(6)

    # 判断市场 (上海 SH, 深圳 SZ, 北京 BJ)
    if code6.startswith(("6", "9", "688")):
        market = "SH"
    elif code6.startswith(("8", "4", "92")):
        market = "BJ"
    else:
        market = "SZ"

    # 如果原始输入带有显式市场标记，以显式标记为准
    if "SH" in raw:
        market = "SH"
    elif "SZ" in raw:
        market = "SZ"
    elif "BJ" in raw:
        market = "BJ"

    prefix = f"{market.lower()}{code6}"
    suffix = f"{code6}.{market}"

    return {
        "code6": code6,
        "prefix": prefix,
        "suffix": suffix,
        "market": market
    }

