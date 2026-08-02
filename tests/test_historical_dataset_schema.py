"""
test_historical_dataset_schema.py — Tests for Historical Dataset Schema & Contract Compliance.
"""

import json
from pathlib import Path


def test_golden_historical_dataset_schema_and_size():
    golden_file = Path(__file__).parent / "data" / "golden" / "historical_golden_dataset.json"
    with open(golden_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    assert len(cases) >= 20, f"Expected at least 20 golden symbols, got {len(cases)}"
    
    delisted_found = any(c["status"] == "DELISTED" for c in cases)
    assert delisted_found is True, "Golden Dataset must include at least 1 delisted stock for Survivorship Bias testing"
