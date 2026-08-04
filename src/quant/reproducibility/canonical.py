"""
canonical.py — Canonical Serialization Engine & SHA-256 Hashing.

This is the SINGLE authoritative canonicalization implementation for the codebase. Every
research-identity, dataset-manifest, and result hash MUST route through `to_canonical_json`
/ `compute_canonical_sha256` — no other module may define a competing JSON/hash
serialization for anything that needs to be reproducible or comparable across runs.

Canonicalization rules (applied recursively BEFORE json.dumps, so they hold for every value
in the structure — including floats nested inside dicts/lists/dataclasses, which json's
`default=` hook alone cannot reach because native floats never trigger it):

  dict       -> keys coerced to str, sorted lexicographically by json.dumps(sort_keys=True);
                each value canonicalized recursively.
  list/tuple -> each element canonicalized recursively; ORDER IS PRESERVED (not sorted) since
                sequence order is semantically meaningful (e.g. a daily price series).
  str        -> passed through unchanged.
  bool       -> passed through unchanged (checked before int: bool is an int subclass).
  int        -> passed through unchanged (arbitrary precision, exact).
  float      -> rounded to 6 decimal places via round(x, 6). This absorbs floating-point
                operation-order noise (e.g. 0.1+0.2 == 0.30000000000000004 in raw IEEE-754)
                so mathematically-equivalent computations hash identically. NaN / Infinity /
                -Infinity are REJECTED (raises ValueError): a non-finite float in a result
                manifest indicates a computation error, not a value that should be silently
                hashed as if it were valid data.
  None       -> passed through unchanged.
  datetime   -> obj.isoformat() (str).
  date       -> obj.isoformat() (str).
  Enum       -> obj.value, canonicalized recursively (covers both str-mixin enums and plain
                enums with non-str values).
  Decimal    -> str(obj) — the exact decimal representation. Never coerced to float first,
                which would reintroduce binary floating-point rounding error for
                currency-like values.
  dataclass  -> {field_name: canonicalized_value} using dataclasses.fields(); frozen or not.
  numpy      -> any object exposing .item() from the `numpy` module (e.g. np.float64,
  scalar        np.int64) is unwrapped via .item() and canonicalized as its native Python
                equivalent, so numeric results computed via numpy hash identically to the
                same value computed in pure Python.
  obj with   -> obj.to_dict(), canonicalized recursively.
  to_dict()
  anything   -> FAILS EXPLICITLY (raises TypeError). There is no default=str escape hatch:
  else          silently stringifying an unrecognized type could hash a __repr__ that
                doesn't uniquely identify the underlying value, hiding a bug instead of
                surfacing it. Add explicit handling here if a new type needs to be hashed.
"""

import hashlib
import json
import math
from dataclasses import is_dataclass, fields as dataclass_fields
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Any


def _canonicalize(obj: Any) -> Any:
    if obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError(f"FAIL CLOSED: cannot canonicalize non-finite float value: {obj!r}")
        return round(obj, 6)
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return _canonicalize(obj.value)
    if isinstance(obj, dict):
        return {str(k): _canonicalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canonicalize(v) for v in obj]
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _canonicalize(getattr(obj, f.name)) for f in dataclass_fields(obj)}
    if type(obj).__module__ == "numpy" and hasattr(obj, "item"):
        return _canonicalize(obj.item())
    if hasattr(obj, "to_dict"):
        return _canonicalize(obj.to_dict())
    raise TypeError(
        f"FAIL CLOSED: cannot canonicalize object of type {type(obj).__name__}. Add explicit "
        "handling to canonical.py's _canonicalize() rather than silently stringifying an "
        "unrecognized type."
    )


def to_canonical_json(data: Any) -> str:
    """Serializes python objects to a deterministic JSON string with sorted keys."""
    canonical = _canonicalize(data)
    return json.dumps(canonical, sort_keys=True, ensure_ascii=True, indent=2, allow_nan=False)


def compute_canonical_sha256(data: Any) -> str:
    """Computes cryptographic SHA-256 hash of the canonical JSON representation."""
    canonical_str = to_canonical_json(data)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
