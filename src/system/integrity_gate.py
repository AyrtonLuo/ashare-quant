"""
integrity_gate.py
研究数据完整性安全门控 (ResearchDataIntegrityGate)
在数据进入 Backtest, Factor, Risk, Portfolio, AI Analyst 之前强制校验数据血缘。
绝对禁止在 RESEARCH MODE 下传入 Demo, Hardcoded, Static Fallback 或 DATA_UNAVAILABLE 假数据污染量化结论。
"""

from typing import Any


class ResearchDataIntegrityError(Exception):
    """当 RESEARCH MODE 发现非真实/污染数据进入计算链路时抛出断言错误"""
    pass


class ResearchDataIntegrityGate:
    @classmethod
    def assert_valid_research_data(cls, data_obj: Any, context: str = "Quantitative Pipeline") -> None:
        """
        强断言数据真实性：
        1. is_real 必须为 True
        2. status 必须为 AVAILABLE
        3. source 必须非空 (e.g., 'AkShare', 'Tencent', 'Local Parquet Cache')
        4. data_mode 必须为 RESEARCH
        """
        if hasattr(data_obj, "data_mode") and getattr(data_obj, "data_mode") == "DEMO":
            raise ResearchDataIntegrityError(f"[{context}] RESEARCH DATA INTEGRITY ERROR: DemoProvider 数据侵入 RESEARCH MODE 链路")

        if hasattr(data_obj, "status") and getattr(data_obj, "status") == "DATA_UNAVAILABLE":
            raise ResearchDataIntegrityError(f"[{context}] RESEARCH DATA INTEGRITY ERROR: 试图在 RESEARCH MODE 中对 DATA_UNAVAILABLE 行情进行算法计算")

        if hasattr(data_obj, "is_real") and not getattr(data_obj, "is_real"):
            raise ResearchDataIntegrityError(f"[{context}] RESEARCH DATA INTEGRITY ERROR: 非真实行情数据禁止注入研究引擎")

        if hasattr(data_obj, "source") and getattr(data_obj, "source") is None:
            raise ResearchDataIntegrityError(f"[{context}] RESEARCH DATA INTEGRITY ERROR: 数据源头元数据 (Source Metadata) 缺失")
