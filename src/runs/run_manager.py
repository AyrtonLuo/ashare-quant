"""
run_manager.py
运行任务管理与执行追踪系统 (RunManager & RunRecord)
记录所有后台/手动任务 (Research Run, Backtest Run, Daily Job, Report Run) 的生命周期状态、耗时与 Error Log。
"""

import os
import json
import time
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import pandas as pd

logger = logging.getLogger("run_manager")
RUNS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "runs")


def get_git_hash() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"


@dataclass
class RunRecord:
    run_id: str
    run_type: str  # "Daily Update", "Backtest Run", "Research Run", "Report Run"
    status: str    # "PENDING", "RUNNING", "SUCCESS", "FAILED", "CANCELLED"
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: float = 0.0
    error: Optional[str] = None
    data_hash: str = "v2.0_parquet"
    git_commit: str = field(default_factory=get_git_hash)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_type": self.run_type,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": round(self.duration_seconds, 2),
            "error": self.error,
            "data_hash": self.data_hash,
            "git_commit": self.git_commit
        }


class RunManager:
    def __init__(self, runs_dir: str = RUNS_DIR):
        self.runs_dir = runs_dir
        os.makedirs(self.runs_dir, exist_ok=True)
        self.runs_file = os.path.join(self.runs_dir, "runs.json")

    def start_run(self, run_id: str, run_type: str) -> RunRecord:
        now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        record = RunRecord(
            run_id=run_id,
            run_type=run_type,
            status="RUNNING",
            start_time=now_str
        )
        self._save_record(record)
        return record

    def complete_run(self, record: RunRecord, status: str = "SUCCESS", error: Optional[str] = None):
        record.status = status
        record.error = error
        record.end_time = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save_record(record)

    def _save_record(self, record: RunRecord):
        history = self.list_runs()
        updated = False
        for i, item in enumerate(history):
            if item.get("run_id") == record.run_id:
                history[i] = record.to_dict()
                updated = True
                break
        if not updated:
            history.append(record.to_dict())

        try:
            with open(self.runs_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"写入 Runs 记录失败 ({e})")

    def list_runs(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.runs_file):
            return []
        try:
            with open(self.runs_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
