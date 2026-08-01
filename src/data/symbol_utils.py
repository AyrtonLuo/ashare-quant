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
    标准化 A 股代码解析：
    输入例: '600519', 'sh600519', '600519.SH', '000001', 'SZ000001'
    输出 Dict:
    {
        "code6": "600519",
        "prefix": "sh600519",
        "suffix": "600519.SH",
        "market": "SH"
    }
    """
    raw = str(symbol).strip().upper()

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
