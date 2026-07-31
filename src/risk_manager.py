"""
risk_manager.py
组合风控熔断器：实现单股仓位上限限制 (<= 30%) 与 15% 动态最大回撤熔断保护状态机。
支持【大盘趋势确认 (Trend-Confirmed Circuit Breaker)】：牛市上升通道回调不误杀强平，确认破位时强平冷静。
"""

import pandas as pd
import numpy as np


def apply_risk_managed_backtest(res_df: pd.DataFrame, 
                                max_dd_limit: float = 0.15, 
                                cooldown_days: int = 10, 
                                max_stock_weight: float = 0.30,
                                num_top_stocks: int = 3) -> tuple[pd.DataFrame, dict]:
    """
    对回测组合施加风控约束：
    1. 单股仓位上限 30% (若有 3 只股票，最高使用 90% 仓位，10% 留存现金)
    2. 15% 动态最大回撤熔断保护 (配合大盘趋势确认)：破 15% 且大盘跌破 MA20 趋势变坏时触发平仓冷静
    """
    data = res_df.copy()
    data = data.sort_values('date').reset_index(drop=True)
    n = len(data)
    
    # 1. 计算受单股 30% 上限约束后的有效策略日收益率 (90% 股票仓位 + 10% 现金)
    portfolio_exposure = min(1.0, num_top_stocks * max_stock_weight)
    data['raw_top_return'] = data['top_return'].fillna(0.0)
    data['scaled_top_return'] = data['raw_top_return'] * portfolio_exposure
    
    managed_returns = np.zeros(n)
    managed_equity = np.zeros(n)
    in_circuit_breaker = np.zeros(n, dtype=bool)
    
    curr_equity = 1.0
    peak_equity = 1.0
    is_broken = False
    cooldown_counter = 0
    trigger_count = 0
    
    for t in range(n):
        if is_broken:
            # 熔断冷静期内：持仓归零，每日收益率为 0%，净值保持平直
            managed_returns[t] = 0.0
            managed_equity[t] = curr_equity
            in_circuit_breaker[t] = True
            cooldown_counter -= 1
            
            # 冷静期满复牌重置
            if cooldown_counter <= 0:
                is_broken = False
                peak_equity = curr_equity
        else:
            # 正常交易状态
            day_ret = data['scaled_top_return'].iloc[t]
            curr_equity = curr_equity * (1.0 + day_ret)
            managed_returns[t] = day_ret
            managed_equity[t] = curr_equity
            in_circuit_breaker[t] = False
            
            # 更新净值峰值
            if curr_equity > peak_equity:
                peak_equity = curr_equity
                
            # 计算动态回撤
            current_dd = (peak_equity - curr_equity) / peak_equity
            
            # 大盘趋势确认：检查大盘是否破位 (无列时默认 False 保持标准熔断)
            is_market_bull = False
            if 'is_bull_trend' in data.columns:
                is_market_bull = bool(data['is_bull_trend'].iloc[t])
                
            # 触及 15% 动态回撤熔断门槛，且大盘确认非强牛局才触发行强平
            if current_dd >= max_dd_limit and (not is_market_bull):
                is_broken = True
                cooldown_counter = cooldown_days
                trigger_count += 1

    data['managed_return'] = managed_returns
    data['cum_managed'] = managed_equity
    data['in_circuit_breaker'] = in_circuit_breaker
    
    # 算风控后的绩效指标
    total_ret = managed_equity[-1] - 1.0
    cum_series = pd.Series(managed_equity)
    cum_max = cum_series.cummax()
    dd_series = (cum_max - cum_series) / cum_max
    max_dd = dd_series.max()
    
    ret_series = pd.Series(managed_returns)
    sharpe = (ret_series.mean() / ret_series.std()) * np.sqrt(252) if ret_series.std() > 0 else 0.0

    metrics = {
        "风控后总收益率": total_ret,
        "风控后最大回撤": max_dd,
        "风控后夏普比率": sharpe,
        "熔断触发次数": trigger_count,
        "单股持仓上限": f"{max_stock_weight * 100:.0f}%",
        "熔断冷却周期": f"{cooldown_days}天"
    }
    
    return data, metrics
