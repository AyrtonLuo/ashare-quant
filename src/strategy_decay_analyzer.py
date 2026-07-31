"""
strategy_decay_analyzer.py
策略归因与 Alpha 衰减诊断器：基于 60 日 Rolling IC 动态监控，识别 Alpha 因子失效与衰减信号。
"""

import pandas as pd
import numpy as np


def diagnose_alpha_decay(ic_df: pd.DataFrame, factor_name: str, rolling_window: int = 60) -> dict:
    """
    进行 60 日 Rolling IC 计算与 Alpha 因子衰减诊断
    
    参数:
        ic_df: 包含 'rank_ic' 列的每日 IC DataFrame
        factor_name: 因子名称
        rolling_window: 滚动窗口大小 (默认 60 个交易日)
        
    返回:
        诊断结果字典 (含滚动 IC 序列、衰减预警状态与诊断提示)
    """
    data = ic_df.copy()
    data['rolling_ic_60'] = data['rank_ic'].rolling(window=rolling_window).mean()
    
    latest_rolling_ic = data['rolling_ic_60'].dropna().iloc[-1] if not data['rolling_ic_60'].dropna().empty else 0.0
    latest_ic = data['rank_ic'].iloc[-1] if not data.empty else 0.0
    
    is_decayed = latest_rolling_ic < 0.0
    
    if is_decayed:
        status_str = "⚠️ Alpha 衰减预警 (DECAY_WARNING)"
        warning_msg = (f"⚠️ 警告：当前 Alpha 因子【{factor_name}】表现衰减！"
                       f"(最近 60 日 Rolling IC = {latest_rolling_ic:.4f} < 0)，"
                       f"建议进入闭环重新挖掘新因子。")
    else:
        status_str = "✅ 因子预测力健康 (HEALTHY)"
        warning_msg = (f"✅ 健康：当前 Alpha 因子【{factor_name}】预测能力正常。"
                       f"(最近 60 日 Rolling IC = {latest_rolling_ic:.4f} > 0)。")

    return {
        "factor_name": factor_name,
        "status": status_str,
        "is_decayed": is_decayed,
        "latest_ic": latest_ic,
        "rolling_ic_60": latest_rolling_ic,
        "warning_msg": warning_msg,
        "rolling_df": data
    }
