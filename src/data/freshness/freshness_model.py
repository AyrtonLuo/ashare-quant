"""
freshness_model.py — Data Freshness & Latency Classifier.
"""

from datetime import datetime
from src.data.contracts.temporal import TemporalDataContract, TemporalClassification


class FreshnessModel:
    """Calculates data age and assigns REALTIME vs DELAYED_REALTIME classifications."""

    @staticmethod
    def classify_latency(event_time: datetime, received_at: datetime) -> TemporalClassification:
        latency_sec = (received_at - event_time).total_seconds()
        if latency_sec <= 1.0:
            return TemporalClassification.REALTIME
        elif latency_sec <= 900.0:  # 15 minutes
            return TemporalClassification.DELAYED_REALTIME
        else:
            return TemporalClassification.HISTORICAL

    @staticmethod
    def get_freshness_age_seconds(contract: TemporalDataContract, current_time: datetime) -> float:
        return max(0.0, (current_time - contract.event_time).total_seconds())
