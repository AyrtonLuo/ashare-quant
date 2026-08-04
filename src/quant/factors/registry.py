"""
registry.py — FactorRegistry: the single, mandatory resolution point from factor_id string to
an executable factor implementation (Phase 8A).

A factor_id (e.g. "momentum_20d:v1") is meaningless on its own — it is a promise that some
code will compute something. FactorRegistry is what makes that promise checkable: it is the
only place in this codebase where a factor_id resolves to an actual class + parameters, and
CertifiedResearchRunExecutor is the only caller permitted to use that resolution to drive a
certified backtest. Because factor_definition_hash (bound into ResearchRunIdentity) is always
computed from the exact FactorSpec list handed to FactorRegistry.resolve(), and resolve() is
the only path from that list to an executing BaseFactor instance, there is no code path where
the identity's declared factor configuration and the actually-executed configuration can
diverge — they are hashes of, and resolutions of, the literal same object.

Registration is explicit (no decorator scanning / plugin discovery) and immutable: duplicate
factor_id registration fails closed, exactly like ResearchRunStore/PersistentDatasetManifestStore's
existing immutability pattern. Unknown factor_id at resolve() time fails closed.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple

from src.quant.factors.base import BaseFactor
from src.quant.factors.momentum import PriceMomentumFactor
from src.quant.factors.value import ValuationFactorAdapter
from src.quant.factors.multi_factor import FactorDirection

# "MARKET_DATA" factors consume the corporate-action-adjusted price series.
# "FUNDAMENTAL_DATA" factors consume PIT-filtered FundamentalDataContract records.
DATA_SOURCE_MARKET = "MARKET_DATA"
DATA_SOURCE_FUNDAMENTAL = "FUNDAMENTAL_DATA"
VALID_DATA_SOURCES = {DATA_SOURCE_MARKET, DATA_SOURCE_FUNDAMENTAL}


@dataclass(frozen=True)
class FactorSpec:
    """Caller-supplied request for one factor. This exact object (as a dict, via
    dataclasses.asdict) is what factor_definition_hash is computed from."""
    factor_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FactorDefinition:
    """What FactorRegistry.resolve() produces: the audit-trail record of what will actually run."""
    factor_id: str
    factor_class: str          # fully-qualified class name, for the audit trail
    data_source: str           # DATA_SOURCE_MARKET | DATA_SOURCE_FUNDAMENTAL
    direction: FactorDirection
    parameters: Dict[str, Any]


class FactorRegistry:
    """Explicit, immutable factor_id -> implementation registry."""

    _entries: Dict[str, Tuple[Callable[[Dict[str, Any]], BaseFactor], str, FactorDirection]] = {}

    @classmethod
    def register(
        cls,
        factor_id: str,
        factory: Callable[[Dict[str, Any]], BaseFactor],
        data_source: str,
        direction: FactorDirection,
    ) -> None:
        if data_source not in VALID_DATA_SOURCES:
            raise ValueError(f"FAIL CLOSED: invalid data_source '{data_source}' for factor_id '{factor_id}'.")
        if factor_id in cls._entries:
            raise ValueError(
                f"FAIL CLOSED: factor_id '{factor_id}' is already registered. A factor_id "
                "identifies immutable behavior; register a new versioned id (e.g. ':v2') "
                "instead of re-registering an existing one."
            )
        cls._entries[factor_id] = (factory, data_source, direction)

    @classmethod
    def resolve(cls, spec: FactorSpec) -> Tuple[BaseFactor, FactorDefinition]:
        if spec.factor_id not in cls._entries:
            raise ValueError(f"FAIL CLOSED: unknown factor_id '{spec.factor_id}'.")
        factory, data_source, direction = cls._entries[spec.factor_id]
        try:
            instance = factory(spec.parameters)
        except TypeError as e:
            raise ValueError(
                f"FAIL CLOSED: invalid parameters for factor_id '{spec.factor_id}': {e}"
            )
        definition = FactorDefinition(
            factor_id=spec.factor_id,
            factor_class=f"{type(instance).__module__}.{type(instance).__name__}",
            data_source=data_source,
            direction=direction,
            parameters=spec.parameters,
        )
        return instance, definition

    @classmethod
    def resolve_all(cls, specs: List[FactorSpec]) -> List[Tuple[BaseFactor, FactorDefinition]]:
        if not specs:
            raise ValueError("FAIL CLOSED: factor_definitions must be explicitly supplied and non-empty.")
        seen_ids = set()
        for spec in specs:
            if spec.factor_id in seen_ids:
                raise ValueError(f"FAIL CLOSED: duplicate factor_id '{spec.factor_id}' within one request.")
            seen_ids.add(spec.factor_id)
        return [cls.resolve(spec) for spec in specs]


def _register_builtin_factors() -> None:
    """Registers the Phase 8A minimum-viable factor set. Runs exactly once per process, at
    module import time — Python's import cache guarantees this module body executes only
    once, so registration is NOT wrapped in a try/except here: a genuine duplicate-id
    registration (e.g. from a test exercising FactorRegistry.register() directly) must be
    allowed to fail closed, not be silently swallowed."""
    if "momentum_20d:v1" not in FactorRegistry._entries:
        FactorRegistry.register(
            "momentum_20d:v1",
            lambda params: PriceMomentumFactor(window_days=params.get("window_days", 20)),
            DATA_SOURCE_MARKET,
            FactorDirection.POSITIVE,
        )
    if "value_pe:v1" not in FactorRegistry._entries:
        FactorRegistry.register(
            "value_pe:v1",
            lambda params: ValuationFactorAdapter(metric_type=params.get("metric_type", "pe_ttm")),
            DATA_SOURCE_FUNDAMENTAL,
            FactorDirection.NEGATIVE,  # lower PE is preferred
        )


_register_builtin_factors()
