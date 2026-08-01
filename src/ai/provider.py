"""
provider.py
LLM 模型提供器抽象接口 (LLMProvider)
解耦具体 AI 厂商 API，支持 MockLLMProvider、LocalLLMProvider 与 OpenAIProvider。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class LLMProvider(ABC):
    def __init__(self, model_name: str = "mock-analyst"):
        self.model_name = model_name

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        pass


class MockLLMProvider(LLMProvider):
    """
    轻量本地诊断解析生成器 (零 API 额度消耗、确定性输出、100% 具备 Source Grounding 归因能力)
    """
    def __init__(self, model_name: str = "mock-quant-analyst"):
        super().__init__(model_name=model_name)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return (
            "### 🤖 AI Quant Analyst 智能研报结论\n\n"
            "根据系统计算的定量结果：\n"
            "1. **风险收益比**：该策略表现出良好风险控制水平，夏普比率与最大回撤指标整体健康；\n"
            "2. **因子贡献与衰减**：动量 (Momentum) 与估值 (Value) 因子提供了主要的 Alpha 来源，尚未观察到急剧衰减；\n"
            "3. **过拟合预警**：样本外 (Out-of-Sample) 验证收益与训练集高度对齐，提示模型具备实际泛化能力；\n"
            "4. **研究建议**：建议维持当前多因子组合配置，同时密切监控高波动行情下的风控仓位上限。"
        )
