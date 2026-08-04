"""
test_real_dataset_revision.py — Real dataset revision lineage & non-destructiveness tests.
"""

from datetime import datetime
import pytest
from src.data.revision.revision_model import DataRevision
from src.data.warehouse.real_data_verifier import RealDataVerificationEngine


def test_real_dataset_revision_history(tmp_path):
    engine = RealDataVerificationEngine(audit_dir=str(tmp_path))
    manifest, store, snap_mgr = engine.generate_verification_dataset()

    rev2 = DataRevision(
        record_id="rec_600519_restated", symbol="600519.SH", field="close", effective_date="2021-01-04",
        value=1820.0, provider="tushare_pro_primary", available_at=datetime(2021, 1, 4, 15, 0),
        received_at=datetime(2021, 2, 1, 15, 0), revision_id="rev_600519_v2", dataset_version="ds_v2.0"
    )
    store.add_revision(rev2)

    history = store.get_revision_history("600519.SH", "close", "2021-01-04")
    assert len(history) == 2
    assert history[0].value == 1800.0
    assert history[1].value == 1820.0
