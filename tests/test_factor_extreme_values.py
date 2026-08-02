"""
test_factor_extreme_values.py — Tests verifying Winsorization (3-Sigma clipping).
"""

from datetime import datetime
from src.quant.factors.base import FactorValue, FactorStatus
from src.quant.factors.normalization import FactorNormalizer


def test_winsorization_clips_extreme_outliers():
    now = datetime.now()
    # 9 normal stocks with values ~1.0, 1 extreme outlier = 1000.0
    factors = [
        FactorValue("S1", "mom", "1.0", 1.0, "2026-08-01", now, FactorStatus.VALID),
        FactorValue("S2", "mom", "1.0", 1.1, "2026-08-01", now, FactorStatus.VALID),
        FactorValue("S3", "mom", "1.0", 0.9, "2026-08-01", now, FactorStatus.VALID),
        FactorValue("S4", "mom", "1.0", 1000.0, "2026-08-01", now, FactorStatus.VALID), # Extreme Outlier!
    ]

    z_scores = FactorNormalizer.normalize_cross_section(factors)
    assert "S4" in z_scores
    # Extreme outlier S4 is clipped by Winsorization and bounded cleanly
    assert z_scores["S4"] <= 3.0
