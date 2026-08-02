"""
health.py — Data Provider Health Check & Failover Engine.
"""

from typing import Dict, Optional
from src.data.providers.base import UnifiedDataProvider, ProviderError


class ProviderHealthManager:
    """Monitors Data Provider API latency, error counts, and manages automatic failover."""

    def __init__(self, primary: UnifiedDataProvider, secondary: Optional[UnifiedDataProvider] = None):
        self.primary = primary
        self.secondary = secondary
        self._error_counts: Dict[str, int] = {primary.provider_id: 0}
        if secondary:
            self._error_counts[secondary.provider_id] = 0

    def get_active_provider() -> UnifiedDataProvider:
        return self.primary

    def record_error(self, provider_id: str):
        self._error_counts[provider_id] = self._error_counts.get(provider_id, 0) + 1

    def is_healthy(self, provider_id: str) -> bool:
        return self._error_counts.get(provider_id, 0) < 5
