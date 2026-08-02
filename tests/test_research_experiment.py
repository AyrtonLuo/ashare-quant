"""
test_research_experiment.py — Unit Tests for Research Experiment Engine.
"""

from src.quant.strategies.config import StrategyConfig, UniverseType, RebalanceFrequency
from src.quant.research.experiment import ResearchExperimentRunner


def test_research_experiment_runner():
    cfg = StrategyConfig(
        strategy_id="exp_strat_v1", strategy_version="1.0.0",
        universe_type=UniverseType.CUSTOM_SYMBOLS, symbols=["600519.SH"],
        factor_weights={"momentum": 0.5}, rebalance_frequency=RebalanceFrequency.DAILY
    )
    dataset_payload = [{"symbol": "600519.SH", "price": 1650.0}]

    exp = ResearchExperimentRunner.run_experiment(
        "exp_001", cfg, "ds_v1", dataset_payload, sharpe=1.5, total_return=0.20, max_drawdown=0.05
    )

    assert exp.experiment_id == "exp_001"
    assert exp.run_manifest.reproducibility_status == "VERIFIED"
