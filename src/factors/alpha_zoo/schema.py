"""
schema.py
Alpha 因子定义模型与元数据 Schema (AlphaDefinition)
支持精确元数据记录、看后偏差防护 (Look-Ahead Safe)、A 股兼容性与 License Attribution。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
import pandas as pd


@dataclass
class AlphaDefinition:
    alpha_id: str                          # 因子唯一 ID (例如 "MOM_20D")
    name: str                              # 因子显示名称
    category: str                          # 分类 (Momentum, Reversal, Volatility, Liquidity, Value, Quality)
    description: str                       # 因子逻辑与经济学含义说明
    formula: str                           # 因子数学公式表达
    required_fields: List[str]             # 必需的数据列 (如 ["close", "volume"])
    warmup_period: int                     # 预热回溯期 (天)
    holding_period: int = 5                # 预设持仓周期 (天)
    frequency: str = "daily"               # 频率 (daily, weekly, intraday)
    source: str = "Internal"               # 来源 (Kakushadze 101, Microsoft Qlib, GTJA191, Academic, Internal)
    license: str = "MIT / Open Academic"    # 开源许可协议
    attribution: str = ""                  # 版权与引用声明
    original_reference: str = ""           # 论文/研报文献引用
    lookahead_safe: bool = True            # 是否通过看后偏差 (Look-Ahead Bias) 断言测试
    requires_fundamental: bool = False     # 是否依赖财务基本面数据 (需 PIT 检验)
    requires_market_data: bool = True      # 是否依赖行情数据 (OHLCV)
    is_a_share_compatible: bool = True     # 是否完全兼容 A 股 T+1 及涨跌停规则
    compute_fn: Optional[Callable[[pd.DataFrame], pd.Series]] = field(default=None, repr=False)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alpha_id": self.alpha_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "formula": self.formula,
            "required_fields": self.required_fields,
            "warmup_period": self.warmup_period,
            "holding_period": self.holding_period,
            "frequency": self.frequency,
            "source": self.source,
            "license": self.license,
            "attribution": self.attribution,
            "original_reference": self.original_reference,
            "lookahead_safe": self.lookahead_safe,
            "requires_fundamental": self.requires_fundamental,
            "requires_market_data": self.requires_market_data,
            "is_a_share_compatible": self.is_a_share_compatible
        }
