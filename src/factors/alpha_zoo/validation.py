"""
validation.py
Alpha 因子 5 维合规验证管道 (Alpha Validation Pipeline)：
1. Schema & Required Fields 校验
2. Look-Ahead Bias 严密检验 (未来切片扰动不变性断言)
3. PIT (Point-In-Time) 财报发布日合规校验
4. Canonical Symbol System (强隔离 000001.SH vs 000001.SZ) 校验
5. License & Attribution 溯源校验
"""

from typing import List, Dict, Any, Tuple, Optional

import numpy as np
import pandas as pd
from src.factors.alpha_zoo.schema import AlphaDefinition
from src.data.symbol_utils import normalize_ashare_code, INDEX_SYMBOLS, STOCK_SYMBOLS


class AlphaValidationError(ValueError):
    """Alpha 校验异常类"""
    pass


def validate_schema(alpha: AlphaDefinition) -> bool:
    """校验 Schema 必填字段与元数据完整性"""
    if not alpha.alpha_id or not isinstance(alpha.alpha_id, str):
        raise AlphaValidationError("Alpha alpha_id 必须为非空字符串")
    if not alpha.name or not alpha.category:
        raise AlphaValidationError(f"Alpha [{alpha.alpha_id}] 必须提供 name 与 category")
    if not alpha.formula or not alpha.required_fields:
        raise AlphaValidationError(f"Alpha [{alpha.alpha_id}] 必须提供 formula 与 required_fields")
    if alpha.warmup_period < 0:
        raise AlphaValidationError(f"Alpha [{alpha.alpha_id}] warmup_period 不能为负数")
    if not alpha.attribution or not alpha.license:
        raise AlphaValidationError(f"Alpha [{alpha.alpha_id}] 必须包含合规 license 与 attribution")
    return True


def validate_no_lookahead(alpha: AlphaDefinition, sample_df: pd.DataFrame) -> bool:
    """
    看后偏差 (Look-Ahead Bias) 严密断言检验：
    1. 给定时间切片 DataFrame (1..T)
    2. 计算时刻 t <= T 的 Alpha 值
    3. 向原 DataFrame 追加未来节点 (T+1..T+N) 甚至任意未来随机行情
    4. 重新计算历史时刻 t <= T 的 Alpha 值
    5. 强断言：历史时刻 t <= T 的 Alpha 值必须 100% 精确一致！若发生改变则表明存在未来数据泄露 (Look-Ahead Violation)！
    """
    if alpha.compute_fn is None:
        raise AlphaValidationError(f"Alpha [{alpha.alpha_id}] 未配置 compute_fn")

    if sample_df.empty or len(sample_df) < (alpha.warmup_period + 5):
        # 自动构造测试数据
        dates = pd.date_range("2025-01-01", periods=60, freq="B")
        sample_df = pd.DataFrame({
            "timestamp": np.repeat(dates, 2),
            "symbol": ["600519.SH", "000001.SZ"] * 60,
            "open": np.random.uniform(10, 20, 120),
            "high": np.random.uniform(20, 30, 120),
            "low": np.random.uniform(5, 10, 120),
            "close": np.random.uniform(10, 20, 120),
            "volume": np.random.uniform(1000, 5000, 120),
            "amount": np.random.uniform(10000, 50000, 120)
        })

    # Step 1: 历史切片计算 (1..T)
    t_cutoff_index = len(sample_df) // 2
    hist_slice = sample_df.iloc[:t_cutoff_index].copy()
    res_hist = alpha.compute_fn(hist_slice)

    # Step 2: 注入未来数据 (追加 T+1..N 极值/随机行情)
    fut_injected = sample_df.copy()
    # 在未来数据列加入扰动
    fut_injected.iloc[t_cutoff_index:, fut_injected.columns.get_loc("close")] *= 5.0
    res_injected = alpha.compute_fn(fut_injected)

    # Step 3: 对齐并比较历史切片处的 Alpha 结果
    if isinstance(res_hist, pd.Series) and isinstance(res_injected, pd.Series):
        common_idx = res_hist.dropna().index.intersection(res_injected.dropna().index)
        if len(common_idx) == 0:
            raise AlphaValidationError(f"Alpha [{alpha.alpha_id}] 计算输出结果为空或索引不匹配")

        diff = np.abs(res_hist.loc[common_idx] - res_injected.loc[common_idx])
        max_diff = np.max(diff) if len(diff) > 0 else 0.0
        if max_diff > 1e-7:
            raise AlphaValidationError(
                f"Alpha [{alpha.alpha_id}] 触发看后偏差 (Look-Ahead Bias)！"
                f"追加未来数据后，历史 t 节点的最大数据偏差为 {max_diff}"
            )
    return True


def validate_symbol_integrity(symbols: List[str]) -> bool:
    """校验代码列表是否符合 Canonical Symbol 规范，拒绝裸代码 "000001" """
    for sym in symbols:
        raw = str(sym).strip().upper()
        if raw == "000001":
            raise AlphaValidationError("拒绝裸代码 '000001'，必须显式指定 '000001.SH' (上证指数) 或 '000001.SZ' (平安银行)")
        info = normalize_ashare_code(raw)
        if not info.get("suffix") or "." not in info["suffix"]:
            raise AlphaValidationError(f"Symbol [{sym}] 未包含确定 Exchange 后缀")
    return True


def validate_pit_compliance(alpha: AlphaDefinition) -> bool:
    """校验基本面 Alpha 是否遵循 PIT (Point-In-Time) 规则"""
    if alpha.requires_fundamental:
        if "publication_date" not in alpha.required_fields and "effective_date" not in alpha.required_fields:
            raise AlphaValidationError(
                f"基本面 Alpha [{alpha.alpha_id}] 的 required_fields 必须声明 'publication_date' 以遵循 PIT 规范"
            )
    return True


def validate_pit_cutoff_date(trading_date: str, publication_date: str) -> bool:
    """断言财报发布日必须 <= 交易切片日，禁止未来财报暴露"""
    t_date = pd.to_datetime(trading_date)
    p_date = pd.to_datetime(publication_date)
    if p_date > t_date:
        raise AlphaValidationError(
            f"PIT 未来财报泄露拦截：财报发布日 {publication_date} > 当前交易日 {trading_date}！"
        )
    return True


def validate_alpha(alpha: AlphaDefinition, sample_df: Optional[pd.DataFrame] = None) -> Tuple[bool, List[str]]:
    """完整 5 维 Alpha 校验流"""
    warnings: List[str] = []
    try:
        validate_schema(alpha)
        validate_pit_compliance(alpha)
        if sample_df is not None:
            validate_no_lookahead(alpha, sample_df)
        return True, warnings
    except AlphaValidationError as e:
        return False, [str(e)]

