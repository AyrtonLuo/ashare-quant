"""
experiment.py — Research Experiment Engine for multi-factor experiment execution & tracking.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List
from src.quant.reproducibility.manifest import ResearchRunManager, ResearchRunManifest


@dataclass(frozen=True)
class ResearchExperiment:
    experiment_id: str
    strategy_config: Any
    run_manifest: ResearchRunManifest


class ResearchExperimentRunner:
    """Executes Multi-Factor Research Experiments and records SHA-256 Run Manifests."""

    @staticmethod
    def run_experiment(
        experiment_id: str,
        strategy_config: Any,
        dataset_id: str,
        dataset_payload: Any,
        sharpe: float,
        total_return: float,
        max_drawdown: float
    ) -> ResearchExperiment:
        manifest = ResearchRunManager.create_run_manifest(
            run_id=experiment_id,
            created_at=datetime.now().isoformat(),
            dataset_id=dataset_id,
            dataset_payload=dataset_payload,
            strategy_id=strategy_config.strategy_id,
            strategy_version=strategy_config.strategy_version,
            parameters=strategy_config.factor_weights,
            cost_model_version="1.0.0",
            sharpe_ratio=sharpe,
            total_return=total_return,
            max_drawdown=max_drawdown
        )
        return ResearchExperiment(experiment_id, strategy_config, manifest)
