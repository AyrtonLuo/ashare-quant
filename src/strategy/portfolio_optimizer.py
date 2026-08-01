"""
portfolio_optimizer.py
资金容量自适应组合配置与买入清单生成器：
1. 资金容量自适应持仓计算器 (auto_calculate_portfolio_size): 根据总投资资金额自动推荐持仓股票数 N
2. 一手 (100股) 零碎股限制过滤与高价股剔除顺延 (filter_and_allocate_portfolio)
3. 生成交易下单清单与权重点阵
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, Any, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("portfolio_optimizer")


def auto_calculate_portfolio_size(total_capital: float) -> int:
    """
    根据总投资资金量自动估算推荐持仓股票数量 N：
    • < 10万元 ──► 自动推荐 5 只
    • 10万 ~ 50万元 ──► 自动推荐 8 只
    • 50万 ~ 200万元 ──► 自动推荐 12 只
    • > 200万元 ──► 自动推荐 15 只
    """
    cap = float(total_capital)
    if cap < 100000:
        return 5
    elif cap < 500000:
        return 8
    elif cap < 2000000:
        return 12
    else:
        return 15


def filter_and_allocate_portfolio(
    ranked_stocks_df: pd.DataFrame,
    total_capital: float,
    target_count: int,
    max_position_cap: float = 1.0
) -> Dict[str, Any]:
    """
    二次精选与 1 手 (100股) 建仓约束过滤分配算法：
    1. 根据 Alpha 得分正向分配权重
    2. 计算每只股票拟买入金额，强制向下取整为 100 股整数倍
    3. 若某高价股票资金分配不足买入 100 股 (0 手)，自动剔除并顺延补齐下一只优质标的
    """
    if ranked_stocks_df is None or ranked_stocks_df.empty:
        return {"portfolio_df": pd.DataFrame(), "total_allocated": 0.0, "cash_left": total_capital, "skipped_stocks": []}

    df = ranked_stocks_df.copy()
    avail_cap = float(total_capital) * float(max_position_cap)

    allocated_rows = []
    skipped_rows = []

    # 遍历选股池，挑选能满 100 股建仓的标的直到达到 target_count
    for idx, row in df.iterrows():
        if len(allocated_rows) >= target_count:
            break

        sym = str(row['symbol']).zfill(6)
        name = str(row['name'])
        price = float(row.get('close', 10.0))
        if price <= 0:
            continue

        # 估算平均单股分配资金
        eq_weight = 1.0 / target_count
        target_amount = avail_cap * eq_weight

        # 强制向下取整为 100 股整数倍
        hands = int(target_amount // (price * 100))
        shares = hands * 100

        # 若价格过高导致不够买 1 手 (100股)
        if shares < 100:
            logger.info(f"股票 {sym} ({name}) 最新价 ¥{price:.2f} 导致资金 ¥{target_amount:.2f} 不够购买 1 手 (100股)，自动剔除并顺延...")
            skipped_rows.append({"symbol": sym, "name": name, "price": price, "reason": "资金不足购买 1 手 (100股)"})
            continue

        actual_amount = shares * price
        allocated_rows.append({
            "symbol": sym,
            "name": name,
            "close": price,
            "AI推荐星级": row.get("AI推荐星级", "⭐⭐⭐⭐⭐"),
            "推荐理由标签": row.get("推荐理由标签", "🔥 优质选股"),
            "COMPOSITE_ALPHA_norm": row.get("COMPOSITE_ALPHA_norm", 1.0),
            "target_weight_pct": round(eq_weight * 100, 2),
            "shares": shares,
            "actual_amount": round(actual_amount, 2)
        })

    result_df = pd.DataFrame(allocated_rows)

    if not result_df.empty:
        # 重新归一化真实权重
        total_used = float(result_df['actual_amount'].sum())
        result_df['target_weight_pct'] = (result_df['actual_amount'] / total_used * 100).round(2)
        cash_left = total_capital - total_used
    else:
        total_used = 0.0
        cash_left = total_capital

    return {
        "portfolio_df": result_df,
        "total_allocated": round(total_used, 2),
        "cash_left": round(cash_left, 2),
        "skipped_stocks": skipped_rows
    }
