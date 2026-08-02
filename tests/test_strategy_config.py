"""
test_strategy_config.py — Unit Tests for Strategy Configuration & Rebalance Calendar Engine.
"""

from src.quant.strategies.config import StrategyConfig, RebalanceFrequency, UniverseType, RebalanceCalendarEngine


def test_strategy_config_and_rebalance_filtering():
    cfg = StrategyConfig(
        strategy_id="multi_v1",
        strategy_version="1.0.0",
        universe_type=UniverseType.CUSTOM_SYMBOLS,
        symbols=["600519.SH"],
        factor_weights={"momentum": 0.5},
        rebalance_frequency=RebalanceFrequency.WEEKLY
    )

    days = [f"2026-08-0{i}" for i in range(1, 15)]
    weekly_days = RebalanceCalendarEngine.filter_rebalance_dates(days, RebalanceFrequency.WEEKLY)
    
    assert cfg.max_position_limit == 0.20
    assert len(weekly_days) < len(days)
