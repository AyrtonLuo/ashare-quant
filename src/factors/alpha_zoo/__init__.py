"""
__init__.py
Alpha Zoo 模块入口与自动初始化注册
"""

from src.factors.alpha_zoo.schema import AlphaDefinition
from src.factors.alpha_zoo.registry import AlphaRegistry
from src.factors.alpha_zoo.validation import (
    validate_alpha,
    validate_no_lookahead,
    validate_pit_compliance,
    validate_symbol_integrity,
    AlphaValidationError
)
from src.factors.alpha_zoo.adapter import AlphaFactorAdapter
from src.factors.alpha_zoo.metadata import load_initial_alphas

# 自动注册初始 Alpha 因子
load_initial_alphas(AlphaRegistry)

__all__ = [
    "AlphaDefinition",
    "AlphaRegistry",
    "AlphaFactorAdapter",
    "validate_alpha",
    "validate_no_lookahead",
    "validate_pit_compliance",
    "validate_symbol_integrity",
    "AlphaValidationError"
]
