"""
test_multi_factor_engine.py — Unit Tests for MultiFactorEngine & Factor Directions.
"""

from src.quant.factors.multi_factor import MultiFactorEngine, FactorWeightConfig, FactorDirection


def test_multi_factor_composite_scoring():
    configs = [
        FactorWeightConfig("momentum", 0.5, FactorDirection.POSITIVE),
        FactorWeightConfig("volatility", 0.5, FactorDirection.NEGATIVE)  # Lower vol = better
    ]
    engine = MultiFactorEngine(configs)

    matrices = {
        "momentum": {"600519.SH": 1.0, "000001.SZ": -1.0},
        "volatility": {"600519.SH": -0.5, "000001.SZ": 0.5}  # Maotai lower vol (-0.5), Pingan higher (0.5)
    }

    scores = engine.compute_composite_scores(matrices)
    # Maotai: +1.0*0.5 + (-(-0.5))*0.5 = 0.5 + 0.25 = 0.75
    assert scores["600519.SH"] == 0.75
    # Pingan: -1.0*0.5 + (-(0.5))*0.5 = -0.5 - 0.25 = -0.75
    assert scores["000001.SZ"] == -0.75
