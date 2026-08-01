# 🤖 Phase 16 Step 3 — Agent Tool Registry & Integrity Tools Report

**Document Version**: 1.0.0  
**Project**: AI Quant Pro (`ashare-quant`)  
**Phase Objective**: 建立统一、安全、可审计、受 Permission 与 Evidence Layer 约束的 Agent Tool 架构 (`src/research/tools/`)。  
**Safety Protocol**: **绝不上漏逻辑至 ReAct Agent，绝不绕过 ResearchDataIntegrityGate，绝不直接调取底层 HTTP/Parquet API。**  

---

## 1. 核心验收状态矩阵 (Step 3 Acceptance Status)

| 验收项目 (Acceptance Item) | 验证标准与实现 (Criteria & Implementation) | 状态 (Status) |
| :--- | :--- | :---: |
| **1. Tool Registry** | `AgentToolRegistry` 实现 `register()`, `get()`, `list_all()`, `search()`, `execute()`，拒绝重复注册与未知工具 | **PASS** |
| **2. Market Tools** | `get_market_quote`, `get_historical_prices`, `get_index_snapshot` 强制走 `MarketDataContract` 与 `ResearchDataIntegrityGate` | **PASS** |
| **3. Factor Tools** | `list_available_factors`, `compute_factor`, `compare_factors` 统一对接 `AlphaRegistry` 并输出 `AlphaEvidenceRecord` | **PASS** |
| **4. Research Tools** | `run_factor_analysis`, `calculate_factor_correlation`, `calculate_factor_decay` 复用 `ResearchService` | **PASS** |
| **5. Risk Tools** | `get_portfolio_exposure`, `get_barra_exposure`, `run_stress_test` 复用 `ExposureCalculator` 与 `PortfolioStressTester` | **PASS** |
| **6. Backtest Tools** | `run_backtest`, `run_walk_forward`, `compare_strategies` 统一复用现有回测引擎与 OOS 验证器 | **PASS** |
| **7. Integrity Tools** | `validate_research_data`, `validate_alpha`, `validate_pit`, `validate_no_lookahead`, `validate_symbol`, `validate_provenance` 阻断假行情侵入 | **PASS** |
| **8. Permission System** | `ToolPermission` (READ_ONLY, RESEARCH, BACKTEST, PORTFOLIO, SYSTEM)，拒绝越权执行 | **PASS** |
| **9. Evidence Trace** | 每次工具执行自动生成 `ToolExecutionRecord` 存证卡片并生成 SHA-256 `result_hash` | **PASS** |
| **10. Research/Demo Isolation**| Research Mode 下行情故障强抛 `DATA_UNAVAILABLE`，绝对禁止回退至 Demo/Mock | **PASS** |
| **11. Canonical Symbol** | 强校验规范代码，强隔离 `000001.SH` (上证指数) 与 `000001.SZ` (平安银行)，拒绝裸代码 `000001` | **PASS** |
| **12. Raw Provider Block** | Agent Tool 绝对禁止包含 `requests.get`, `pd.read_parquet`, `akshare` 原生 API 直连 | **PASS** |

---

## 2. 架构设计与文件分布 (Architecture & File Mapping)

系统在 `src/research/tools/` 目录下新增了 9 个模块，包含 18 个 Approved Agent Tools：

```text
src/research/tools/
├── __init__.py                # 模块初始化与 18 个 Approved Tool 自动注册
├── base.py                    # AgentTool 基类, ToolPermission, ToolExecutionContext, ToolResult, ToolExecutionRecord
├── registry.py                # AgentToolRegistry 中央注册表 (单例鉴权与留痕)
├── market_tools.py            # GetMarketQuoteTool, GetHistoricalPricesTool, GetIndexSnapshotTool
├── factor_tools.py            # ListAvailableFactorsTool, ComputeFactorTool, CompareFactorsTool
├── research_tools.py          # RunFactorAnalysisTool, CalculateFactorCorrelationTool, CalculateFactorDecayTool
├── risk_tools.py              # GetPortfolioExposureTool, GetBarraExposureTool, RunStressTestTool
├── backtest_tools.py          # RunBacktestTool, RunWalkForwardTool, CompareStrategiesTool
└── integrity_tools.py        # ValidateResearchDataTool, ValidateAlphaTool, ValidatePITTool, ValidateNoLookaheadTool, ValidateSymbolTool, ValidateProvenanceTool
```

---

## 3. 权限控制模型 (Tool Permission Boundary)

为防御 Agent 潜在的越权风险，建立了严格的 `ToolPermission` 权限等级：

- **`READ_ONLY`**: 只读行情与元数据；
- **`RESEARCH`**: 因子计算、交叉相关性与归因研究；
- **`BACKTEST`**: 策略回测与 Walk-Forward 验证；
- **`PORTFOLIO`**: 组合持仓与风险分解查询；
- **`SYSTEM`**: 系统底层配置 (默认禁给 Agent)。

**Agent 默认权限集合**: `{READ_ONLY, RESEARCH, BACKTEST, PORTFOLIO}`。  
当 Agent 试图调用超越其授权范围的 Tool 时，`AgentToolRegistry.execute()` 立即拦截并返回 `ToolPermissionError`。

---

## 4. 全血缘 Trace 与 ToolExecutionRecord

每次 Tool 被派发执行，Registry 均会自动记录留痕存证卡片 (`ToolExecutionRecord`)：

```json
{
  "run_id": "run_20260801_141516",
  "tool_name": "compute_factor",
  "arguments_hash": "a1b2c3d4e5f6",
  "execution_timestamp": "2026-08-01T14:15:16.123456",
  "data_mode": "RESEARCH",
  "is_real": true,
  "status": "SUCCESS",
  "result_hash": "e2e8071d9f7f87b3"
}
```

---

## 5. 测试套件与 Commit 状态 (Test Results & Git Lineage)

- **新增测试文件**: [tests/test_agent_tools.py](file:///Users/yuhanluo/ashare-quant/tests/test_agent_tools.py) (含 16 项单元与端到端集成测试)
- **全量 Pytest 汇总**: **226 Passed, 0 Failed, 100% GREEN** (耗时 9.94 秒)
- **Git Branch**: `main`
- **Git Commit Hash**: `aafd08b` (以及当前提交)
- **Commit Message**: `feat(agent): implement auditable AgentToolRegistry and integrity tools`

---

## 6. Step 4 暂停提示 (Phase 16 Step 3 Completion & Pause)

🛑 **状态说明**:  
Phase 16 Step 3 (Agent Tool Registry & Integrity Tools Layer) 已全部完成并经过 226 项 Pytest 100% 绿灯验证。  
按照要求，**暂不进入 Step 4 (ReAct Agent / Planner)**，等待用户审核与指引。
