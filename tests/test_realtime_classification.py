"""
test_realtime_classification.py — Tests for Latency and Real-Time Data Classification.
"""

from datetime import datetime, timedelta
from src.data.freshness.freshness_model import FreshnessModel
from src.data.contracts.temporal import TemporalClassification


def test_realtime_latency_under_1s():
    event_time = datetime(2026, 8, 1, 10, 31, 5, 0)
    received_at = datetime(2026, 8, 1, 10, 31, 5, 180000)  # 180ms
    cls = FreshnessModel.classify_latency(event_time, received_at)
    assert cls == TemporalClassification.REALTIME


def test_delayed_realtime_latency():
    event_time = datetime(2026, 8, 1, 10, 31, 0, 0)
    received_at = datetime(2026, 8, 1, 10, 31, 10, 0)  # 10s delay
    cls = FreshnessModel.classify_latency(event_time, received_at)
    assert cls == TemporalClassification.DELAYED_REALTIME
