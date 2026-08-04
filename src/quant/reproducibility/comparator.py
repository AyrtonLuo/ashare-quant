"""
comparator.py — ResearchResultComparator for detailed diff comparison between Research Runs.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Tuple, Optional
from src.quant.reproducibility.identity import ResearchRunIdentity
from src.quant.reproducibility.manifest import ResearchInputManifest, ResearchResultManifest


class ComparisonStatus(str, Enum):
    MATCH = "MATCH"
    DIFFERENT_INPUT = "DIFFERENT_INPUT"
    DIFFERENT_RESULT = "DIFFERENT_RESULT"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class RunComparisonReport:
    run_id_a: str
    run_id_b: str
    status: ComparisonStatus
    difference_reason: str
    input_differences: list
    result_differences: list


class ResearchResultComparator:
    """
    Compares two research runs and provides detailed human-readable difference reasons.
    """

    @staticmethod
    def compare_runs(
        identity_a: ResearchRunIdentity,
        identity_b: ResearchRunIdentity,
        input_manifest_a: Optional[ResearchInputManifest] = None,
        input_manifest_b: Optional[ResearchInputManifest] = None,
        result_manifest_a: Optional[ResearchResultManifest] = None,
        result_manifest_b: Optional[ResearchResultManifest] = None
    ) -> RunComparisonReport:
        input_diffs = []
        result_diffs = []

        # 1. Compare Inputs
        if identity_a.snapshot_id != identity_b.snapshot_id:
            input_diffs.append(f"snapshot_id differs: '{identity_a.snapshot_id}' vs '{identity_b.snapshot_id}'")
        if identity_a.dataset_version != identity_b.dataset_version:
            input_diffs.append(f"dataset_version differs: '{identity_a.dataset_version}' vs '{identity_b.dataset_version}'")
        if identity_a.as_of != identity_b.as_of:
            input_diffs.append(f"as_of differs: '{identity_a.as_of}' vs '{identity_b.as_of}'")
        if identity_a.universe_hash != identity_b.universe_hash:
            input_diffs.append(f"universe_hash differs: '{identity_a.universe_hash}' vs '{identity_b.universe_hash}'")
        if identity_a.factor_definition_hash != identity_b.factor_definition_hash:
            input_diffs.append(f"factor_definition_hash differs: '{identity_a.factor_definition_hash}' vs '{identity_b.factor_definition_hash}'")
        if identity_a.parameter_hash != identity_b.parameter_hash:
            input_diffs.append(f"parameter_hash differs: '{identity_a.parameter_hash}' vs '{identity_b.parameter_hash}'")
        if identity_a.transaction_cost_model_hash != identity_b.transaction_cost_model_hash:
            input_diffs.append(f"transaction_cost_model_hash differs: '{identity_a.transaction_cost_model_hash}' vs '{identity_b.transaction_cost_model_hash}'")
        if identity_a.input_hash != identity_b.input_hash:
            input_diffs.append(f"input_hash differs: '{identity_a.input_hash}' vs '{identity_b.input_hash}'")

        if input_diffs:
            reason = "DIFFERENT_INPUT: " + "; ".join(input_diffs)
            return RunComparisonReport(
                run_id_a=identity_a.research_run_id,
                run_id_b=identity_b.research_run_id,
                status=ComparisonStatus.DIFFERENT_INPUT,
                difference_reason=reason,
                input_differences=input_diffs,
                result_differences=[]
            )

        # 2. Compare Results
        if identity_a.result_hash != identity_b.result_hash:
            result_diffs.append(f"result_hash differs: '{identity_a.result_hash}' vs '{identity_b.result_hash}'")

        if result_manifest_a and result_manifest_b:
            if result_manifest_a.equity_curve_hash != result_manifest_b.equity_curve_hash:
                result_diffs.append(f"equity_curve_hash differs: '{result_manifest_a.equity_curve_hash}' vs '{result_manifest_b.equity_curve_hash}'")
            if result_manifest_a.performance_metrics_hash != result_manifest_b.performance_metrics_hash:
                result_diffs.append(f"performance_metrics_hash differs: '{result_manifest_a.performance_metrics_hash}' vs '{result_manifest_b.performance_metrics_hash}'")

        if result_diffs:
            reason = "DIFFERENT_RESULT: " + "; ".join(result_diffs)
            return RunComparisonReport(
                run_id_a=identity_a.research_run_id,
                run_id_b=identity_b.research_run_id,
                status=ComparisonStatus.DIFFERENT_RESULT,
                difference_reason=reason,
                input_differences=[],
                result_differences=result_diffs
            )

        return RunComparisonReport(
            run_id_a=identity_a.research_run_id,
            run_id_b=identity_b.research_run_id,
            status=ComparisonStatus.MATCH,
            difference_reason="MATCH: All input parameters and result hashes are identical.",
            input_differences=[],
            result_differences=[]
        )
