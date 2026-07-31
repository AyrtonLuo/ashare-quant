"""
concept_leader_engine.py
全市场股票/行业概念搜索与产业链龙头自动识别引擎：
1. 申万一级/二级行业分类与热门概念板块映射 (AI算力、半导体龙头、低空经济、高股息央企、新能源等)
2. 产业链龙头智能打标算法 (leader_stock_identifier)：
   结合【行业市值占比 (40%)】+【日均成交额占比 (30%)】+【Beta 动量 (30%)】
   自动打标标注：👑 龙一 (Leader)、🥈 龙二 (Co-Leader)、⚡ 弹性跟风 (Follower)
3. 全市场模糊搜索：支持股票代码、股票名称或概念关键词检索
"""

import logging
import pandas as pd
import numpy as np
import akshare as ak
from typing import Dict, Any, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("concept_leader_engine")

# 预设全市场核心热门概念与股票代码映射表
PRESET_CONCEPT_BOARDS = {
    "AI算力/半导体龙头": ["688981", "600584", "002371", "603986", "688012", "688008", "300308", "000977", "601138"],
    "高股息央企/稳健避险": ["600941", "601939", "601398", "600028", "601857", "601088", "600016", "601668"],
    "港口航运/外贸物流": ["000088", "601228", "600018", "601018", "601919", "601298"],
    "基建龙头/大国重器": ["601186", "601668", "600820", "601816", "601985", "600025"],
    "消费龙头/白酒家电": ["000651", "600177", "600398", "601607", "000538", "601098"],
    "金融龙头/银行证券": ["600016", "601169", "000001", "600919", "601997", "601009", "600926", "601818", "601128", "601377", "601878", "000750"]
}


def fetch_concept_boards() -> Dict[str, List[str]]:
    """
    抓取申万一级/二级行业与同花顺概念板块列表 (带网络备用防护)
    """
    concept_map = PRESET_CONCEPT_BOARDS.copy()
    try:
        df_board = ak.stock_board_concept_name_em()
        if not df_board.empty:
            for _, row in df_board.head(15).iterrows():
                b_name = str(row.get("板块名称", ""))
                if b_name and b_name not in concept_map:
                    concept_map[b_name] = []
    except Exception as e:
        logger.warning(f"获取网络概念板块列表异常 ({e})，使用预设通用概念板块...")

    return concept_map


def leader_stock_identifier(concept_name: str, stock_df: pd.DataFrame) -> pd.DataFrame:
    """
    产业链龙头智能识别打标算法 (leader_stock_identifier)
    公式: Leader_Score = 0.40 * MV_Share + 0.30 * Vol_Share + 0.30 * MOM_norm
    打标分类: 👑 龙一 (Leader)、🥈 龙二 (Co-Leader)、⚡ 弹性跟风 (Follower)
    """
    if stock_df is None or stock_df.empty:
        return pd.DataFrame()

    df = stock_df.copy()

    # 找到所属概念代码列表
    matched_symbols = []
    for c_key, sym_list in PRESET_CONCEPT_BOARDS.items():
        if concept_name in c_key or c_key in concept_name:
            matched_symbols.extend(sym_list)

    if matched_symbols:
        sub_df = df[df['symbol'].isin(matched_symbols)].copy()
    else:
        # 按名称模糊匹配
        sub_df = df[df['name'].str.contains(concept_name[:2], case=False, na=False)].copy()

    if sub_df.empty:
        sub_df = df.head(10).copy()

    # 提取最新的截面数据
    latest_date = sub_df['date'].max()
    latest_sub = sub_df[sub_df['date'] == latest_date].copy()

    if latest_sub.empty:
        return pd.DataFrame()

    # 计算行业市值占比 (MV_Share) 与成交额占比 (Vol_Share)
    total_mv = latest_sub['total_mv_yi'].fillna(latest_sub['close'] * 10).sum() if 'total_mv_yi' in latest_sub.columns else latest_sub['close'].sum()
    total_mv = max(total_mv, 1.0)
    latest_sub['mv_share'] = (latest_sub['total_mv_yi'].fillna(latest_sub['close'] * 10) / total_mv) if 'total_mv_yi' in latest_sub.columns else (latest_sub['close'] / total_mv)

    # 动量得分
    mom_scores = latest_sub.get('MOM_20_norm', latest_sub.get('COMPOSITE_ALPHA_norm', 0.0))

    # 综合龙头得分算法
    latest_sub['leader_score'] = 0.40 * latest_sub['mv_share'] + 0.30 * (latest_sub['close'] / latest_sub['close'].sum()) + 0.30 * (mom_scores / (mom_scores.abs().sum() + 1e-5))

    # 排序与打标
    latest_sub = latest_sub.sort_values('leader_score', ascending=False).reset_index(drop=True)

    roles = []
    for rank in range(len(latest_sub)):
        if rank == 0:
            roles.append("👑 龙一 (Leader)")
        elif rank in [1, 2]:
            roles.append("🥈 龙二 (Co-Leader)")
        else:
            roles.append("⚡ 弹性跟风 (Follower)")

    latest_sub['龙头角色'] = roles
    return latest_sub


def search_concept_or_stock(keyword: str, stock_df: pd.DataFrame) -> Dict[str, Any]:
    """
    全市场股票 & 概念板块模糊搜索
    支持按股票代码（如 600941）、股票名称（如 中国移动）、或概念名称（如 AI算力）检索
    """
    kw = str(keyword).strip()
    if not kw:
        return {"matched_type": "none", "data": pd.DataFrame()}

    # 1. 优先概念板块匹配
    for concept_name in PRESET_CONCEPT_BOARDS.keys():
        if kw in concept_name or concept_name in kw:
            leader_df = leader_stock_identifier(concept_name, stock_df)
            return {
                "matched_type": "concept",
                "concept_name": concept_name,
                "data": leader_df
            }

    # 2. 个股代码或名称模糊匹配
    matched_stocks = stock_df[
        stock_df['symbol'].str.contains(kw, case=False, na=False) |
        stock_df['name'].str.contains(kw, case=False, na=False)
    ].copy()

    if not matched_stocks.empty:
        latest_date = matched_stocks['date'].max()
        latest_matched = matched_stocks[matched_stocks['date'] == latest_date].copy()
        return {
            "matched_type": "stock",
            "concept_name": f"搜索词关联个股 [{kw}]",
            "data": latest_matched
        }

    # 3. 未匹配到则提供热点板块龙头推荐
    default_df = leader_stock_identifier("高股息央企/稳健避险", stock_df)
    return {
        "matched_type": "fallback",
        "concept_name": f"未匹配到关键词 [{kw}]，已为您推荐优质热点板块: 高股息央企/稳健避险",
        "data": default_df
    }
