"""
futu_trader.py
富途 OpenD 港股模拟交易执行引擎 (macOS 原生集成本地 Futu OpenD 网关 TrdMarket.HK)
核心功能：
1. A 股 / 港股代码至富途港股规范格式转换 (如 600941 -> HK.00941, 00700 -> HK.00700)
2. 连接 127.0.0.1:11111 富途港股模拟盘上下文 (TrdMarket.HK)，查询资金与持仓
3. 智能调仓 (Portfolio Rebalance)：非 Top 39 旧持仓全额平仓，新 Top 39 标按 <=30% 风控与 100 股一手整倍数挂单买入
4. 容错与模拟降级：若 OpenD 未启动，优雅降级为 Mock/Dry-Run 引擎
5. 连接生命周期管理：在 finally 块中必须执行 trd_ctx.close() 释放套接字连接
"""

import logging
import pandas as pd
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("futu_trader")

# 尝试导入 futu SDK
try:
    from futu import (
        OpenTrdContext,
        TrdEnv,
        TrdMarket,
        TrdSide,
        OrderType,
        RET_OK,
        SecurityFirm
    )
    HAS_FUTU_SDK = True
except ImportError:
    HAS_FUTU_SDK = False
    logger.warning("未检测到 futu-api 包，将默认开启 Mock 试跑模式。")

# A 股 -> 港股通 / AH 股港股代码映射表
AH_STOCK_MAP = {
    "600941": "HK.00941",  # 中国移动
    "601398": "HK.01398",  # 工商银行
    "601939": "HK.00939",  # 建设银行
    "601288": "HK.01288",  # 农业银行
    "601988": "HK.03988",  # 中国银行
    "600036": "HK.03968",  # 招商银行
    "601318": "HK.02318",  # 中国平安
    "601628": "HK.02628",  # 中国人寿
    "601899": "HK.02899",  # 紫金矿业
    "002594": "HK.01211",  # 比亚迪
    "601919": "HK.01919",  # 中远海控
    "600016": "HK.01988",  # 民生银行
    "601169": "HK.01169",  # 北京银行
    "601668": "HK.03311",  # 中国建筑 (中国建筑国际)
    "600919": "HK.03618",  # 重庆农商行 / 江苏银行
    "601816": "HK.06016",  # 京沪高铁
    "600050": "HK.00762",  # 中国联通
    "601818": "HK.06818",  # 光大银行
    "601607": "HK.02607",  # 上海医药
    "601377": "HK.03377",  # 兴业证券
    "601985": "HK.01816",  # 中国核电
}


def to_futu_hk_code(symbol: str) -> str:
    """
    将 A 股 / 港股代码转换为富途港股规范格式 (如 600941 -> HK.00941, 00700 -> HK.00700)
    """
    sym_str = str(symbol).strip()
    
    # 1. 若已有 HK. 前缀，直接返回
    if sym_str.upper().startswith("HK."):
        return sym_str.upper()

    # 2. 若在 AH 映射表中，直接映射
    if sym_str in AH_STOCK_MAP:
        return AH_STOCK_MAP[sym_str]

    # 3. 若为 5 位数字港股代码 (如 00700, 09988)
    if len(sym_str) <= 5 and sym_str.isdigit():
        return f"HK.{sym_str.zfill(5)}"

    # 4. 若为 6 位 A 股代码且未在映射表中，自动生成规范 HK 5位代码格式 (如 600018 -> HK.60018)
    if len(sym_str) == 6 and sym_str.isdigit():
        return f"HK.{sym_str[1:]}"

    return f"HK.{sym_str.zfill(5)}"


def to_ashare_symbol(futu_code: str) -> str:
    """将富途规范格式还原为通用 5-6 位股票代码 (如 HK.00941 -> 00941)"""
    if "." in str(futu_code):
        return str(futu_code).split(".")[1]
    return str(futu_code)


class FutuSimTrader:
    """富途港股模拟交易执行器 (TrdMarket.HK)"""

    def __init__(self, host: str = "127.0.0.1", port: int = 11111, is_mock: bool = False):
        self.host = host
        self.port = port
        self.is_mock = is_mock or not HAS_FUTU_SDK

    def execute_rebalance(self, top_portfolio_df: pd.DataFrame, initial_mock_cash: float = 1000000.0, mock_positions: Dict = None) -> Dict[str, Any]:
        """
        根据 Top 39 优质选股名单对富途港股模拟盘账号 (TrdMarket.HK) 执行智能调仓
        """
        top_portfolio = top_portfolio_df.copy()
        top_portfolio['futu_code'] = top_portfolio['symbol'].apply(to_futu_hk_code)
        target_futu_codes = set(top_portfolio['futu_code'])

        sell_orders: List[Dict[str, Any]] = []
        buy_orders: List[Dict[str, Any]] = []
        
        mode = "Mock Simulated Engine (HK Market)"
        total_assets = initial_mock_cash
        available_cash = initial_mock_cash
        market_value = 0.0

        trd_ctx = None
        is_connected = False

        if not self.is_mock and HAS_FUTU_SDK:
            try:
                # 初始化富途交易上下文 (连接 Mac 本地 OpenD 网关)
                trd_ctx = OpenTrdContext(
                    host=self.host,
                    port=self.port,
                    is_encrypt=False,
                    security_firm=SecurityFirm.FUTUSECURITIES
                )
                mode = "Real OpenD Gateway (HK Market, 127.0.0.1:11111)"
                is_connected = True
                logger.info(f"✅ 成功连接至 Mac 本地富途 OpenD 网关 ({self.host}:{self.port}, 港股模拟盘)！")
            except Exception as e:
                logger.warning(f"无法连接至富途 OpenD 网关 ({e})，系统自动优雅降级为 Mock 试跑模式。")
                mode = f"Mock Engine (OpenD 连线降级: {e})"
                is_connected = False

        try:
            current_positions: Dict[str, Dict[str, Any]] = {}

            if is_connected and trd_ctx is not None:
                # 1. 查询富途港股模拟盘账户资金状况 (TrdMarket.HK)
                ret_acc, acc_df = trd_ctx.accinfo_query(trd_env=TrdEnv.SIMULATE, acc_id=0, trd_market=TrdMarket.HK)
                if ret_acc == RET_OK and not acc_df.empty:
                    acc_row = acc_df.iloc[0]
                    total_assets = float(acc_row.get('total_assets', initial_mock_cash))
                    available_cash = float(acc_row.get('cash', initial_mock_cash))
                    market_value = float(acc_row.get('market_val', 0.0))

                # 2. 查询富途港股模拟盘当前持仓 (TrdMarket.HK)
                ret_pos, pos_df = trd_ctx.position_list_query(trd_env=TrdEnv.SIMULATE, acc_id=0, trd_market=TrdMarket.HK)
                if ret_pos == RET_OK and not pos_df.empty:
                    for _, pos_row in pos_df.iterrows():
                        code = str(pos_row['code'])
                        qty = int(pos_row['qty'])
                        price = float(pos_row['cost_price'])
                        name = str(pos_row.get('stock_name', ''))
                        if qty > 0:
                            current_positions[code] = {"qty": qty, "price": price, "name": name}
            else:
                # 若显式传入了测试旧持仓，则加载；新空账户默认持仓为空 {}
                current_positions = mock_positions if mock_positions is not None else {}

            # =========================================================================
            # 🛍️ 步骤 1: 卖出逻辑 (当前持仓中不在 Top 39 名单内的港股标的全额卖出)
            # =========================================================================
            for code, pos in current_positions.items():
                if code not in target_futu_codes:
                    sym = to_ashare_symbol(code)
                    qty_to_sell = pos['qty']
                    price = pos['price']
                    name = pos['name']
                    
                    status = "Mock Sold (HK)"
                    if is_connected and trd_ctx is not None:
                        ret_order, order_df = trd_ctx.place_order(
                            price=price,
                            qty=qty_to_sell,
                            code=code,
                            trd_side=TrdSide.SELL,
                            order_type=OrderType.NORMAL,
                            trd_env=TrdEnv.SIMULATE,
                            trd_market=TrdMarket.HK
                        )
                        status = "OpenD Submitted (HK)" if ret_order == RET_OK else f"Order Failed ({order_df})"

                    sell_orders.append({
                        "futu_code": code,
                        "symbol": sym,
                        "name": name,
                        "sell_qty": qty_to_sell,
                        "price": price,
                        "sell_amount": round(qty_to_sell * price, 2),
                        "status": status
                    })
                    
                    # 资金回流
                    available_cash += qty_to_sell * price

            # =========================================================================
            # 🛒 步骤 2: 买入逻辑 (Top 39 中未持有的港股标的按 30% 风控与 100 股整倍数买入)
            # =========================================================================
            new_targets = top_portfolio[~top_portfolio['futu_code'].isin(current_positions.keys())]
            num_new = len(new_targets)

            if num_new > 0:
                # 资金预算分配：每只单股上限 ≤ 30% 账户总资产，且不超过可用资金均分
                max_stock_budget = total_assets * 0.30
                per_stock_budget = min(max_stock_budget, available_cash / num_new)

                for _, row in new_targets.iterrows():
                    code = row['futu_code']
                    sym = row['symbol']
                    name = row['name']
                    price = float(row['close'])

                    if price <= 0:
                        continue

                    # =====================================================================
                    # 🚨 【工程规范】：100 股最小一手交易单位约束 (向下取整)
                    # =====================================================================
                    buy_qty = int(per_stock_budget // (price * 100)) * 100

                    if buy_qty < 100:
                        logger.info(f"股票 {name}({code}) 可用预算不足买入 100 股一手单位，跳过。")
                        continue

                    buy_amount = round(buy_qty * price, 2)
                    status = "Mock Bought (HK)"

                    if is_connected and trd_ctx is not None:
                        ret_order, order_df = trd_ctx.place_order(
                            price=price,
                            qty=buy_qty,
                            code=code,
                            trd_side=TrdSide.BUY,
                            order_type=OrderType.NORMAL,
                            trd_env=TrdEnv.SIMULATE,
                            trd_market=TrdMarket.HK
                        )
                        status = "OpenD Submitted (HK)" if ret_order == RET_OK else f"Order Failed ({order_df})"

                    buy_orders.append({
                        "futu_code": code,
                        "symbol": sym,
                        "name": name,
                        "buy_qty": buy_qty,
                        "price": price,
                        "buy_amount": buy_amount,
                        "status": status
                    })
                    
                    available_cash -= buy_amount
                    market_value += buy_amount

        finally:
            # =========================================================================
            # 🚨 【工程规范】：在 finally 块中必须执行 trd_ctx.close() 释放套接字连接
            # =========================================================================
            if trd_ctx is not None:
                try:
                    trd_ctx.close()
                    logger.info("🔒 富途 OpenD 港股交易上下文连接已安全关闭释放。")
                except Exception as ex:
                    logger.warning(f"关闭交易上下文发生小异常: {ex}")

        return {
            "mode": mode,
            "sell_orders": sell_orders,
            "buy_orders": buy_orders,
            "account_summary": {
                "total_assets": round(total_assets, 2),
                "cash": round(max(0.0, available_cash), 2),
                "market_value": round(market_value, 2)
            }
        }
