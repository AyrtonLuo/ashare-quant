"""
metadata.py
Alpha 因子元数据注册清单与分类检索注册函数。
"""

from src.factors.alpha_zoo.schema import AlphaDefinition
from src.factors.alpha_zoo.momentum import MOM_5D_DEF, MOM_20D_DEF, MOM_60D_DEF
from src.factors.alpha_zoo.reversal import REV_5D_DEF, REV_20D_DEF
from src.factors.alpha_zoo.volatility import VOL_20D_DEF
from src.factors.alpha_zoo.liquidity import TURNOVER_20D_DEF
from src.factors.alpha_zoo.value import EP_TTM_DEF

INITIAL_ALPHAS = [
    MOM_5D_DEF,
    MOM_20D_DEF,
    MOM_60D_DEF,
    REV_5D_DEF,
    REV_20D_DEF,
    VOL_20D_DEF,
    TURNOVER_20D_DEF,
    EP_TTM_DEF,
]


def load_initial_alphas(registry_cls):
    """装载初始 Alpha 因子集合至 AlphaRegistry"""
    for alpha in INITIAL_ALPHAS:
        try:
            registry_cls.register(alpha)
        except Exception:
            pass
