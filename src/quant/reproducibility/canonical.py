"""
canonical.py — Canonical Serialization Engine & SHA-256 Hashing.
Enforces deterministic ordering, float formatting, and timestamp representations for reproducibility.
"""

import hashlib
import json
from datetime import datetime
from typing import Any


def _canonical_converter(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, float):
        # Deterministic float rounding to 6 decimal places
        return round(obj, 6)
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)


def to_canonical_json(data: Any) -> str:
    """
    Serializes python objects to a deterministic JSON string with sorted keys.
    """
    return json.dumps(
        data,
        sort_keys=True,
        default=_canonical_converter,
        ensure_ascii=True,
        indent=2
    )


def compute_canonical_sha256(data: Any) -> str:
    """
    Computes cryptographic SHA-256 hash of canonical JSON representation.
    """
    canonical_str = to_canonical_json(data)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
