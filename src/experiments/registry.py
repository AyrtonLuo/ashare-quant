"""
registry.py
轻量级量化实验注册表 (ExperimentRegistry)
记录实验配置、因子权重、参数、数据集版本与 Git Commit Hash，支持历史实验落盘与复现比对。
"""

import os
import json
import logging
import subprocess
from dataclasses import dataclass, field
import pandas as pd
from typing import Dict, Any, List, Optional

logger = logging.getLogger("experiment_registry")
EXP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "experiments")


def get_git_commit_hash() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"


@dataclass
class ExperimentRecord:
    experiment_id: str
    timestamp: str
    strategy_id: str
    factor_config: Dict[str, float]
    parameters: Dict[str, Any]
    universe: List[str]
    date_range: str
    benchmark: str
    performance_metrics: Dict[str, Any]
    git_commit: str = field(default_factory=get_git_commit_hash)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "timestamp": self.timestamp,
            "strategy_id": self.strategy_id,
            "factor_config": self.factor_config,
            "parameters": self.parameters,
            "universe": self.universe,
            "date_range": self.date_range,
            "benchmark": self.benchmark,
            "performance_metrics": self.performance_metrics,
            "git_commit": self.git_commit
        }


class ExperimentRegistry:
    def __init__(self, exp_dir: str = EXP_DIR):
        self.exp_dir = exp_dir
        os.makedirs(self.exp_dir, exist_ok=True)

    def register_experiment(self, record: ExperimentRecord) -> str:
        filepath = os.path.join(self.exp_dir, f"{record.experiment_id}.json")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"实验 {record.experiment_id} 已落盘至 {filepath}")
        except Exception as e:
            logger.error(f"写入实验记录 {filepath} 失败 ({e})")
        return filepath

    def list_experiments(self) -> List[Dict[str, Any]]:
        results = []
        if not os.path.exists(self.exp_dir):
            return results
        for fname in sorted(os.listdir(self.exp_dir)):
            if fname.endswith(".json"):
                fpath = os.path.join(self.exp_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        results.append(json.load(f))
                except Exception:
                    pass
        return results
