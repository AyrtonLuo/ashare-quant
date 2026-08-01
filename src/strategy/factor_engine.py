"""
factor_engine.py
自适应因子加权模型 (Adaptive Factor Allocation Engine)：
1. 市场大盘 MA20 趋势与全球宏观情绪联动判定
2. 顺风/牛市 (Risk-On)：MOM 权重提升至 60%，解锁 100% 满仓捕抓主升浪
3. 逆风/熊市 (Risk-Off)：LOW_VOL 权重提升至 70%，切换为高股息避险模式，仓位降至 60%
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("factor_engine")


def build_adaptive_alpha_factor(df_processed: pd.DataFrame, macro_sentiment: float = 0.0, style: str = "⚖️ 攻守兼备型 (自适应)") -> pd.DataFrame:
    """
    支持 4 大 AI 动态交易风格配置模型 (Style Configurator Engine)：
    1. 🛡️ 极客防守型: LOW_VOL 70%, 仓位 60%
    2. ⚡ 激进进攻型: MOM 70%, 全仓 100% 抓主升浪
    3. ⚖️ 攻守兼备型 (自适应): 基于大盘 MA20 与全球宏观 S_macro 动态加权
    4. 📰 新闻催化型: 重磅 ⭐️4~5 权威新闻 Alpha 加权提升至 40%
    """
    res_df = df_processed.copy()
    res_df = res_df.sort_values(['date', 'symbol']).reset_index(drop=True)

    # 1. 计算每日横截面市场大盘均价与 20 日均线 (MA20)
    market_daily = res_df.groupby('date')['close'].mean().reset_index(name='market_close')
    market_daily['market_ma20'] = market_daily['market_close'].rolling(window=20, min_periods=5).mean()
    market_daily['is_bull_trend'] = market_daily['market_close'] >= market_daily['market_ma20']

    # 映射回主 Dataframe (先清除可能存在的旧同名列，防多重后缀键名报错)
    drop_cols = [c for c in ['market_close', 'market_ma20', 'is_bull_trend', 'is_bull_trend_x', 'is_bull_trend_y'] if c in res_df.columns]
    if drop_cols:
        res_df = res_df.drop(columns=drop_cols)
    res_df = res_df.merge(market_daily[['date', 'market_close', 'market_ma20', 'is_bull_trend']], on='date', how='left')

    # 2. 逐日按行情状态与选择的交易风格自适应调整因子权重
    dates = res_df['date'].drop_duplicates().sort_values()

    comp_raw_series = pd.Series(index=res_df.index, dtype=float)
    target_pos_series = pd.Series(index=res_df.index, dtype=float)
    regime_series = pd.Series(index=res_df.index, dtype=str)

    for curr_date in dates:
        mask = (res_df['date'] == curr_date)
        day_sample = res_df[mask]

        if day_sample.empty:
            continue

        is_bull = bool(day_sample['is_bull_trend'].iloc[0])

        # =========================================================================
        # 🚨 AI 动态交易风格配置
        # =========================================================================
        if "极客防守型" in style:
            w_mom = 0.00
            w_vol = 0.70
            w_dev = 0.30
            w_sent = 0.00
            target_cap = 0.60
            regime_label = "🛡️ 极客防守型 (LOW_VOL 70%, 仓位60%)"

        elif "激进进攻型" in style:
            w_mom = 0.70
            w_vol = 0.00
            w_dev = 0.10
            w_sent = 0.20
            target_cap = 1.00
            regime_label = "⚡ 激进进攻型 (MOM 70%, 满仓抓主升浪)"

        elif "新闻催化型" in style:
            w_mom = 0.30
            w_vol = 0.20
            w_dev = 0.10
            w_sent = 0.40
            target_cap = 0.90
            regime_label = "📰 新闻催化型 (⭐️4~5星新闻 Alpha 40%)"

        else:
            # 默认：⚖️ 攻守兼备型 (自适应)
            if is_bull and macro_sentiment >= -0.1:
                w_mom = 0.60
                w_vol = 0.20
                w_dev = 0.20
                w_sent = 0.25
                target_cap = 1.00
                regime_label = "🟢 自适应牛市 (Risk-On, MOM 60%)"
            elif (not is_bull) or macro_sentiment < -0.3:
                w_mom = 0.10
                w_vol = 0.70
                w_dev = 0.20
                w_sent = 0.10
                target_cap = 0.60
                regime_label = "🔴 自适应熊市 (Risk-Off, LowVol 70%)"
            else:
                w_mom = 0.35
                w_vol = 0.35
                w_dev = 0.30
                w_sent = 0.20
                target_cap = 0.85
                regime_label = "🟡 自适应震荡 (Neutral)"

        mom_col = day_sample['MOM_20_norm'].fillna(0.0) if 'MOM_20_norm' in day_sample.columns else day_sample.get('MOM_20', 0.0)
        vol_col = day_sample['LOW_VOL_20_norm'].fillna(0.0) if 'LOW_VOL_20_norm' in day_sample.columns else day_sample.get('LOW_VOL_20', 0.0)
        dev_col = day_sample['MA_DEV_20_norm'].fillna(0.0) if 'MA_DEV_20_norm' in day_sample.columns else day_sample.get('MA_DEV_20', 0.0)
        sent_col = day_sample.get('SENTIMENT_ALPHA', 0.0)

        # 融合加权
        comp_val = w_mom * mom_col + w_vol * vol_col + w_dev * dev_col + w_sent * sent_col
        comp_raw_series[mask] = comp_val
        target_pos_series[mask] = target_cap
        regime_series[mask] = regime_label

    res_df['COMPOSITE_ALPHA_adaptive_raw'] = comp_raw_series
    res_df['target_position_cap'] = target_pos_series
    res_df['market_regime'] = regime_series
    res_df['regime_label'] = regime_series

    # 每日横截面 Z-Score 标准化 (防御性 fillna)
    def zscore(s):
        if s.dropna().empty or len(s.dropna()) < 3 or s.std() < 1e-12:
            return s.fillna(0.0)
        res = (s - s.mean()) / s.std()
        return res.fillna(0.0)

    res_df['COMPOSITE_ALPHA_adaptive_norm'] = res_df.groupby('date')['COMPOSITE_ALPHA_adaptive_raw'].transform(zscore)
    res_df['COMPOSITE_ALPHA_norm'] = res_df['COMPOSITE_ALPHA_adaptive_norm'].fillna(0.0)
    res_df['COMPOSITE_ALPHA'] = res_df['COMPOSITE_ALPHA_norm']

    return res_df
