"""
registry.py
Alpha 因子注册表中心 (AlphaRegistry)：
1. 统一注册、查询、审计与验证所有 AlphaDefinition 因子。
2. 强校验重复注册与非标准键，拦截未授权或可能导致 Look-Ahead Bias 的因子。
3. 提供按类别、关键词检索与一键计算 API。
"""

from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from src.factors.alpha_zoo.schema import AlphaDefinition
from src.factors.alpha_zoo.validation import validate_alpha, AlphaValidationError


class AlphaRegistry:
    """Alpha 因子注册表中心 (Thread-safe Singleton / Central Registry)"""
    _registry: Dict[str, AlphaDefinition] = {}

    @classmethod
    def register(cls, alpha: AlphaDefinition, sample_df: Optional[pd.DataFrame] = None) -> bool:
        """注册 Alpha 因子，必须通过 5 维合规校验"""
        if alpha.alpha_id in cls._registry:
            raise AlphaValidationError(f"Alpha [{alpha.alpha_id}] 已在注册表中存在，禁止静默覆盖！")

        is_valid, warnings = validate_alpha(alpha, sample_df)
        if not is_valid:
            raise AlphaValidationError(f"Alpha [{alpha.alpha_id}] 未通过合规校验: {warnings}")

        cls._registry[alpha.alpha_id] = alpha
        return True

    @classmethod
    def get(cls, alpha_id: str) -> AlphaDefinition:
        """获取指定 AlphaDefinition"""
        key = str(alpha_id).strip().upper()
        if key not in cls._registry:
            raise KeyError(f"AlphaRegistry 中未找到 ID 为 [{alpha_id}] 的因子。当前注册数量: {len(cls._registry)}")
        return cls._registry[key]

    @classmethod
    def list_all(cls) -> List[AlphaDefinition]:
        """列表列出所有已注册 Alpha"""
        return list(cls._registry.values())

    @classmethod
    def list_by_category(cls, category: str) -> List[AlphaDefinition]:
        """按 Category 分类检索"""
        cat_lower = str(category).strip().lower()
        return [a for a in cls._registry.values() if a.category.lower() == cat_lower]

    @classmethod
    def search(cls, keyword: str) -> List[AlphaDefinition]:
        """按关键词全文检索 (ID / Name / Description / Formula)"""
        kw = str(keyword).strip().lower()
        res = []
        for a in cls._registry.values():
            if (kw in a.alpha_id.lower() or 
                kw in a.name.lower() or 
                kw in a.description.lower() or 
                kw in a.formula.lower()):
                res.append(a)
        return res

    @classmethod
    def validate(cls, alpha_id: str, sample_df: Optional[pd.DataFrame] = None) -> Tuple[bool, List[str]]:
        """对指定 Alpha 执行完整断言验证"""
        alpha = cls.get(alpha_id)
        return validate_alpha(alpha, sample_df)

    @classmethod
    def compute(cls, alpha_id: str, data: pd.DataFrame) -> pd.Series:
        """计算指定 Alpha 因子，输出 pandas Series"""
        alpha = cls.get(alpha_id)
        if alpha.compute_fn is None:
            raise AlphaValidationError(f"Alpha [{alpha_id}] 缺少计算逻辑 compute_fn")
        return alpha.compute_fn(data)

    @classmethod
    def clear(cls):
        """仅在 Test Suite 还原环境使用"""
        cls._registry.clear()
