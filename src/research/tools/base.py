"""
base.py
Agent Tool 基础契约、权限模型 (ToolPermission) 与上下文存证模型 (ToolExecutionContext, ToolResult, ToolExecutionRecord)
"""

import hashlib
import json
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Set


class ToolPermission(str, Enum):
    """Tool 权限等级定义"""
    READ_ONLY = "READ_ONLY"      # 只读行情与元数据
    RESEARCH = "RESEARCH"        # 因子计算与归因研究
    BACKTEST = "BACKTEST"        # 策略回测与 Walk-Forward 验证
    PORTFOLIO = "PORTFOLIO"      # 组合管理与持仓查询 (只读)
    SYSTEM = "SYSTEM"            # 系统与底座配置 (默认禁给 Agent)


class ToolPermissionError(PermissionError):
    """Tool 权限越权异常类"""
    pass


@dataclass
class ToolExecutionContext:
    """Tool 执行环境上下文"""
    mode: str = "RESEARCH MODE"
    user_request: str = ""
    run_id: str = field(default_factory=lambda: datetime.now().strftime("run_%Y%m%d_%H%M%S"))
    data_mode: str = "RESEARCH"
    permissions: Set[ToolPermission] = field(default_factory=lambda: {
        ToolPermission.READ_ONLY,
        ToolPermission.RESEARCH,
        ToolPermission.BACKTEST,
        ToolPermission.PORTFOLIO
    })
    evidence_enabled: bool = True
    services: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Tool 统一标准输出数据契约 (绝对禁止直接返回裸 DataFrame)"""
    success: bool
    data: Any
    evidence: Optional[Dict[str, Any]] = None
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None
    result_hash: str = ""

    def __post_init__(self):
        if not self.result_hash and self.success:
            raw_str = f"{self.success}|{type(self.data).__name__}|{self.error}"
            self.result_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "evidence": self.evidence,
            "warnings": self.warnings,
            "error": self.error,
            "result_hash": self.result_hash
        }


@dataclass
class ToolExecutionRecord:
    """Tool 执行留痕与全血缘存证卡片"""
    run_id: str
    tool_name: str
    arguments_hash: str
    execution_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data_sources: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    data_mode: str = "RESEARCH"
    is_real: bool = True
    status: str = "SUCCESS"
    result_hash: str = ""
    evidence_ids: List[str] = field(default_factory=list)


class AgentTool:
    """Agent Tool 基础基类 (Abstract Base Agent Tool)"""
    name: str = ""
    description: str = ""
    input_schema: Dict[str, Any] = {}
    permission: ToolPermission = ToolPermission.READ_ONLY

    def execute(self, context: ToolExecutionContext, **kwargs) -> ToolResult:
        """执行工具，必须重写"""
        raise NotImplementedError("AgentTool 派生类必须实现 execute() 方法")

    def check_permission(self, context: ToolExecutionContext) -> None:
        """断言权限有效性"""
        if self.permission not in context.permissions:
            raise ToolPermissionError(
                f"Agent Tool [{self.name}] 需要权限 [{self.permission.value}]，"
                f"但当前 Agent 仅拥有权限: {[p.value for p in context.permissions]}"
            )
