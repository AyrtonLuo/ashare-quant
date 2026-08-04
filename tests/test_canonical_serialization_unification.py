"""
test_canonical_serialization_unification.py — Phase 7I adversarial tests (Directive 007I,
Section 11). Proves there is exactly one canonical hash contract used everywhere.
"""

from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

import pytest

from src.quant.reproducibility.canonical import to_canonical_json, compute_canonical_sha256
from src.data.domain.manifest import DatasetManifestManager


def test_identical_logical_objects_produce_identical_hashes():
    a = {"symbol": "600519.SH", "price": 100.5, "count": 3}
    b = {"symbol": "600519.SH", "price": 100.5, "count": 3}
    assert compute_canonical_sha256(a) == compute_canonical_sha256(b)


def test_dict_key_insertion_order_does_not_change_hash():
    a = {"z": 1, "a": 2, "m": 3}
    b = {"a": 2, "m": 3, "z": 1}
    assert compute_canonical_sha256(a) == compute_canonical_sha256(b)


def test_list_order_is_preserved_and_affects_hash():
    a = [1, 2, 3]
    b = [3, 2, 1]
    assert compute_canonical_sha256(a) != compute_canonical_sha256(b)


def test_timestamp_representation_is_deterministic():
    dt = datetime(2026, 8, 1, 15, 30, 0)
    h1 = compute_canonical_sha256({"t": dt})
    h2 = compute_canonical_sha256({"t": datetime(2026, 8, 1, 15, 30, 0)})
    assert h1 == h2
    assert '"2026-08-01T15:30:00"' in to_canonical_json({"t": dt})


def test_date_representation_is_deterministic():
    d = date(2026, 8, 1)
    assert '"2026-08-01"' in to_canonical_json({"d": d})


def test_float_operation_order_noise_is_absorbed():
    """0.1 + 0.2 != 0.3 in raw IEEE-754; the canonical hash must treat them as equal."""
    a = 0.1 + 0.2
    b = 0.3
    assert a != b  # sanity: raw floats genuinely differ
    assert compute_canonical_sha256({"x": a}) == compute_canonical_sha256({"x": b})


def test_nan_and_infinity_are_rejected():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        compute_canonical_sha256({"x": float("nan")})
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        compute_canonical_sha256({"x": float("inf")})


def test_enum_canonicalizes_to_its_value():
    class Color(Enum):
        RED = "red"

    assert compute_canonical_sha256({"c": Color.RED}) == compute_canonical_sha256({"c": "red"})


def test_decimal_uses_exact_string_not_float_rounding():
    assert compute_canonical_sha256({"x": Decimal("10.10")}) == compute_canonical_sha256({"x": "10.10"})


def test_dataclass_canonicalizes_deterministically_regardless_of_field_order_definition():
    @dataclass(frozen=True)
    class Point:
        x: float
        y: float

    p1 = Point(x=1.0, y=2.0)
    p2 = {"x": 1.0, "y": 2.0}
    assert compute_canonical_sha256(p1) == compute_canonical_sha256(p2)


def test_unsupported_type_fails_explicitly_not_silently_stringified():
    class Unrecognized:
        pass

    with pytest.raises(TypeError, match="FAIL CLOSED"):
        compute_canonical_sha256({"x": Unrecognized()})


def test_dataset_manifest_hash_and_research_hash_share_one_canonical_contract():
    """manifest.py's DatasetManifestManager must not maintain a second, competing
    serialization implementation — both must agree on the exact same hash for the same input."""
    payload = {"symbol": "600519.SH", "close": 0.1 + 0.2, "ts": datetime(2026, 8, 1, 12, 0, 0)}
    assert DatasetManifestManager.compute_sha256(payload) == compute_canonical_sha256(payload)
