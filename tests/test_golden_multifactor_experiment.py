"""
test_golden_multifactor_experiment.py — Golden Multi-Factor Experiment Verification Tests.
"""

import json
from pathlib import Path


def test_golden_multifactor_experiment_manifest():
    manifest_file = Path(__file__).parent / "data" / "golden" / "golden_multifactor_experiment.json"
    with open(manifest_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["experiment_id"] == "golden_multifactor_exp_v1"
    assert "momentum" in data["factor_weights"]
    assert "value" in data["factor_weights"]
    assert data["expected_sharpe"] > 1.0
