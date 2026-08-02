"""
test_transaction_costs.py — Unit Tests for Transaction Cost Model.
"""

from src.quant.backtest.cost_model import TransactionCostModel


def test_transaction_cost_buy_and_sell():
    cost_model = TransactionCostModel(commission_rate=0.00025, stamp_duty_rate=0.0005, slippage_rate=0.0001)
    
    trade_amt = 100000.0
    buy_cost = cost_model.calculate_trade_cost(trade_amt, is_buy=True)
    sell_cost = cost_model.calculate_trade_cost(trade_amt, is_buy=False)

    # Buy cost: 0.025% comm + 0.01% slip = $35
    assert buy_cost == 35.0
    # Sell cost: 0.025% comm + 0.01% slip + 0.05% stamp duty = $85
    assert sell_cost == 85.0
