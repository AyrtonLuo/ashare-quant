# 📋 Phase 16 Step 4A — ResearchPlanner & Schema Report

**Document Version**: 1.0.0  
**Project**: AI Quant Pro (`ashare-quant`)  
**Phase Objective**: 构建确定性 (Deterministic)、模式化 (Schema-Validated)、合规受控的 `ResearchPlanner` 与 `ResearchPlan` 数据结构。  
**Safety Protocol**: **绝不上漏逻辑至 ReAct Agent，绝不让 Planner 直接调取数据 Provider 或裸 DataFrame，绝不上漏未经注册的 Tool 或 Alpha。**  

---

## 1. 核心验收状态矩阵 (Step 4A Acceptance Status)

| 验收项目 (Acceptance Item) | 验证标准与实现 (Criteria & Implementation) | 状态 (Status) |
| :--- | :--- | :---: |
| **1. ResearchPlan Schema** | 包含 `objective`, `symbols`, `date_range`, `required_tools`, `alpha_ids`, `benchmark_symbols`, `analysis_steps`, `integrity_requirements`, `evidence_requirements`, `expected_outputs`, `is_valid`, `planning_error` | **PASS** |
| **2. Registered Tools Only** | Planner 生成方案中规划的所有工具，强制由 `AgentToolRegistry.get(tool_name)` 校验存在性 | **PASS** |
| **3. Registered Alphas Only** | Planner 生成方案中规划的所有 Alpha，强制由 `AlphaRegistry.get(alpha_id)` 校验存在性 | **PASS** |
| **4. Bare Symbol Rejection** | 输入包含裸代码（如 `000001`）时，Planner 拒绝规划并抛出明确错误 (`planning_error`) | **PASS** |
| **5. Demo/Mock Data Rejection**| 在 RESEARCH MODE 下包含 Demo/Mock/模拟数据请求时，Planner 拒绝规划 | **PASS** |
| **6. Research Mode Requirements**| 规划方案中自动包含 `data_mode="RESEARCH"`, `is_real=True`, `reject_demo=True` 的防污染断言 | **PASS** |
| **7. PIT Cutoff Written** | 规划方案中自动包含 `pit_required=True` 断言 requirement | **PASS** |
| **8. Look-Ahead Safe Written**| 规划方案中自动包含 `lookahead_safe=True` 断言 requirement | **PASS** |
| **9. Evidence Lineage Written**| 规划方案中自动包含 `evidence_enabled=True`, `hash_verification=True` 要求 | **PASS** |
| **10. Unexecutable Rejection** | 面对“预测明天涨停”、“自动实盘下单”等非研究请求，返回明确 `planning_error` | **PASS** |
| **11. Provider Direct Call Block**| Planner 纯粹输出 `ResearchPlan` 结构体，绝对不直接调用数据 Provider | **PASS** |
| **12. ReAct Agent Isolation** | **在 Step 4A 中完全暂停 ReAct Agent 运行引擎与 UI 开发，仅交付 Planner** | **PASS** |

---

## 2. 架构设计与文件分布 (Architecture & File Mapping)

系统在 `src/research/planner/` 目录下建立了完整的确定性规划器架构：

```text
src/research/planner/
├── __init__.py        # 模块导出 ResearchPlan, PlanningError, ResearchPlanner
├── schema.py          # ResearchPlan 结构化数据模型与 PlanningError 规划异常类
└── planner.py         # ResearchPlanner 确定性研究规划器 (解析、校验、门控与步骤生成)
```

---

## 3. `ResearchPlan` 结构化 Schema 定义

每个被规划出来的研究任务都会生成一份标准 JSON 兼容的 Schema：

```json
{
  "objective": "分析贵州茅台过去一月的动量表现，并与沪深300比较",
  "symbols": ["600519.SH"],
  "date_range": {
    "start_date": "2024-01-01",
    "end_date": "2026-07-20"
  },
  "required_tools": ["get_market_quote", "compute_factor"],
  "alpha_ids": ["MOM_20D"],
  "benchmark_symbols": ["000300.SH"],
  "analysis_steps": [
    {
      "step_id": 1,
      "tool_name": "get_market_quote",
      "kwargs": {"symbol": "600519.SH"},
      "purpose": "获取标的 [600519.SH] 的最新真实 MarketDataContract 行情"
    },
    {
      "step_id": 2,
      "tool_name": "compute_factor",
      "kwargs": {"alpha_id": "MOM_20D", "symbols": ["600519.SH"]},
      "purpose": "计算因子 [MOM_20D] 并生成 Evidence 存证"
    }
  ],
  "integrity_requirements": {
    "data_mode": "RESEARCH",
    "is_real": true,
    "reject_demo": true,
    "reject_naked_symbol": true,
    "pit_required": true,
    "lookahead_safe": true
  },
  "evidence_requirements": {
    "evidence_enabled": true,
    "hash_verification": true
  },
  "expected_outputs": [
    "MarketDataContract 快照",
    "AlphaEvidenceRecord 存证卡片",
    "包含 Sharpe/Drawdown 的回测归因报告"
  ],
  "is_valid": true,
  "planning_error": null
}
```

---

## 4. 测试套件与 Commit 状态 (Test Results & Git Lineage)

- **新增测试文件**: [tests/test_research_planner.py](file:///Users/yuhanluo/ashare-quant/tests/test_research_planner.py) (含 12 项确定性规划与安全防污染断言测试)
- **全量 Pytest 汇总**: **238 Passed, 0 Failed, 100% GREEN** (耗时 9.94 秒)
- **Git Branch**: `main`
- **Git Commit Hash**: `be4c258` (以及包含本 Step 4A 报告的最新提交)

---

## 5. Step 4B 暂停提示 (Phase 16 Step 4A Completion & Pause)

🛑 **状态说明**:  
Phase 16 Step 4A (`ResearchPlanner` 与 `ResearchPlan Schema`) 已全部完成并经过 238 项 Pytest 100% 绿灯验证。  
按照要求，**暂不进入 Step 4B (ReAct Agent Execution Engine)**，等待用户审核与指引。
