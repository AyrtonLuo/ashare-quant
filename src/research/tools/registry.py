"""
registry.py
Agent Tool 中央注册表 (AgentToolRegistry)：
1. 统一管理、鉴权、检索与派发执行所有 AgentTool。
2. Agent 严禁自行 import 工具或绕过 Registry 调用底层 API。
"""

import hashlib
from typing import Dict, List, Optional, Any
from src.research.tools.base import (
    AgentTool,
    ToolExecutionContext,
    ToolResult,
    ToolExecutionRecord,
    ToolPermissionError
)


class AgentToolRegistry:
    """Agent Tool 中央注册表 (Central Agent Tool Registry)"""
    _registry: Dict[str, AgentTool] = {}
    _execution_records: List[ToolExecutionRecord] = []

    @classmethod
    def register(cls, tool: AgentTool) -> bool:
        """注册工具，拒绝重复注册"""
        name_key = str(tool.name).strip()
        if not name_key:
            raise ValueError("Tool name 不能为空")
        if name_key in cls._registry:
            raise ValueError(f"AgentTool [{name_key}] 已注册，禁止静默覆盖！")

        cls._registry[name_key] = tool
        return True

    @classmethod
    def get(cls, name: str) -> AgentTool:
        """获取指定 Tool"""
        name_key = str(name).strip()
        if name_key not in cls._registry:
            raise KeyError(f"AgentToolRegistry 中未找到工具 [{name}]。当前注册数量: {len(cls._registry)}")
        return cls._registry[name_key]

    @classmethod
    def list_all(cls) -> List[AgentTool]:
        """列出所有已注册工具"""
        return list(cls._registry.values())

    @classmethod
    def search(cls, keyword: str) -> List[AgentTool]:
        """按关键词检索工具"""
        kw = str(keyword).strip().lower()
        res = []
        for tool in cls._registry.values():
            if kw in tool.name.lower() or kw in tool.description.lower():
                res.append(tool)
        return res

    @classmethod
    def execute(cls, name: str, context: ToolExecutionContext, **kwargs) -> ToolResult:
        """统一派发执行工具，强制安全鉴权与留痕"""
        tool = cls.get(name)

        # 1. 鉴权
        tool.check_permission(context)

        # 2. 生成参数哈希
        arg_str = f"{name}|{sorted(kwargs.items())}"
        arg_hash = hashlib.sha256(arg_str.encode("utf-8")).hexdigest()[:12]

        try:
            # 3. 执行工具
            result = tool.execute(context, **kwargs)

            # 4. 留痕存证
            record = ToolExecutionRecord(
                run_id=context.run_id,
                tool_name=name,
                arguments_hash=arg_hash,
                data_mode=context.data_mode,
                is_real=True if context.data_mode == "RESEARCH" else False,
                status="SUCCESS" if result.success else "FAILED",
                result_hash=result.result_hash
            )
            cls._execution_records.append(record)
            return result

        except Exception as e:
            record = ToolExecutionRecord(
                run_id=context.run_id,
                tool_name=name,
                arguments_hash=arg_hash,
                data_mode=context.data_mode,
                is_real=False,
                status="ERROR",
                result_hash=""
            )
            cls._execution_records.append(record)
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                warnings=[f"Tool [{name}] 执行异常: {str(e)}"]
            )

    @classmethod
    def get_execution_records(cls) -> List[ToolExecutionRecord]:
        """获取所有留痕存证"""
        return list(cls._execution_records)

    @classmethod
    def clear(cls):
        """重置注册表 (仅在测试套件使用)"""
        cls._registry.clear()
        cls._execution_records.clear()
