# System Architecture

## Architecture Overview
AI Quant Pro (`ashare-quant`) 采用分层解耦、单向数据流与受控 Agent Tool 架构。核心架构分为：`Third-Party Data Adapters -> Data Contracts & Integrity Gate -> Quant Services & Factor Engine -> Agent Tool Registry -> ReAct Research Agent & Planner -> Web UI / API Terminal`。

```text
Third-Party APIs (AkShare / Tencent)
       │
       ▼
Provider Adapter Layer (src/data/contract.py: normalize_market_data_contract)
       │
       ▼
ResearchDataIntegrityGate (src/system/integrity_gate.py)
       │
       ▼
Quant Services Layer (app.py: get_services)
       │
       ▼
Agent Tool Registry (src/research/tools/: AgentToolRegistry)
       │
       ▼
ReAct Research Agent & Planner (src/research/agent/, src/research/planner/)
       │
       ▼
Streamlit Web UI / Terminal (app.py)
```

## Technology Stack
- **Language**: Python 3.9+
- **Core Runtime & Web UI**: Streamlit 1.30+
- **Data & Numeric Computing**: Pandas, NumPy, SciPy
- **Data Provider Integrations**: AkShare, Tencent Realtime API
- **Testing & Quality Control**: Pytest 8.4+, Coverage
- **Agent Protocol & Tooling**: ReAct Architecture, SHA-256 Lineage Hashing

## Application Architecture
- `app.py`: 系统入口与 Streamlit 交互渲染界面；
- `src/data/`:
  - `contract.py`: 统一数据契约 (`MarketDataContract`, `HistoricalMarketDataContract`, `FundamentalDataContract`, `MLFeatureContract`, `PredictionContract`, `ExternalDataEvidenceRecord`)；
  - `symbol_utils.py`: Single Source of Truth Symbol 工具库 (Canonical Symbol 格式化与解析)；
  - `pit_provider.py`: PIT 基本面 Provider (`publication_date <= trading_date`)；
- `src/factors/`:
  - `alpha_zoo/`: Alpha 因子注册表与标准化因子算子 (`MOM_20D`, `VOL_20D`, `TURNOVER_20D`, `EP_TTM`)；
  - `engine.py`: FactorEngine 适配器与计算流水线；
- `src/research/`:
  - `tools/`: AgentTool 契约与 `AgentToolRegistry` (18+ 统一工具)；
  - `planner/`: `ResearchPlanner` 确定性规划器；
  - `agent/`: `ReActResearchAgent` 主逻辑环；
  - `skills/`: `SkillRegistry` 技能模版库；
- `src/system/`:
  - `integrity_gate.py`: `ResearchDataIntegrityGate` 数据完整性门控卡片。

## Data Architecture
1. **Canonical Symbol Standard**: `600519.SH`, `000001.SZ`, `000001.SH`, `000300.SH`, `688110.SH`；
2. **Explicit Asset Type Isolation**: `INDEX` (指数) 与 `STOCK` (个股) 在 `normalize_ashare_code` 强隔离；
3. **Data Modes**: `RESEARCH` (真实模式，强断言真实性) vs `DEMO` (演示模式)；
4. **Units**:
   - `close`: `RMB`
   - `volume`: `Shares`
   - `amount`: `RMB`
   - `ROE`: `Ratio` (例如 `0.27` 代表 27%).

## API Architecture
所有内部组件通信必须使用规范化数据契约 (Contract)。第三方底层 API 差异仅在 Adapter 层进行消融，决不上漏。

## AI / ML Architecture
- **Planner**: `ResearchPlanner` 将自然语言研究请求转换为结构化 `ResearchPlan`；
- **Agent**: `ReActResearchAgent` 遵循 `Plan -> Tool -> Observe -> Integrity -> Evidence -> Final` 闭环；
- **Boundary**: Agent 只能使用 `AgentToolRegistry.execute()` 访问功能，严禁裸 DataFrame / Parquet / HTTP 调用。

## Multi-Agent Orchestration
Phase 16 Step 5.1 建立了基于 `ResearchOrchestrator` 的最小可扩展 Multi-Agent 编排引擎：

### Agent Roles
- **ResearchAgent**: 负责假设拆解、规划推演与 ReAct 逻辑综合（复用 `ReActResearchAgent`）；
- **DataAgent**: 负责行情发现、K 线与 PIT 基本面数据拉取（100% 经过 `AgentToolRegistry`）；
- **QuantAgent**: 负责因子计算与 Alpha 分析（对接 `AlphaRegistry` 与 `AgentToolRegistry`）。

### Orchestrator
`ResearchOrchestrator` 负责管理研究生命周期，决定调度的 Agent 角色组合，透传 `ToolExecutionRecord` 存证，并汇总为统一的 `ResearchContext`。

### Research Context & Agent Result
- **ResearchContext**: 包含 `research_id`, `user_query`, `active_agents`, `agent_results`, `tool_execution_records`, `errors`, `status`；
- **AgentResult**: 强类型、可序列化的 Agent 输出结构体，包含 `agent_id`, `agent_role`, `status`, `summary`, `evidence`, `tool_execution_records`, `errors`。

### Permission & Integrity Boundary
所有 Agent 的工具调用 100% 经过 `AgentToolRegistry` 鉴权与 `ResearchDataIntegrityGate` 防线，绝不上漏硬编码或假数据。

### Failure Model
支持强鲁棒单 Agent 异常捕获，单 Agent 失败时不崩溃系统，将 Context 标记为 `PARTIAL` 或 `FAILED` 并记录具体错误归因。

### Future Integration (MCP / API / UI)
Orchestrator 保持 Transport Independent，可直接被 CLI、FastAPI、MCP Server 或 Streamlit 交互层安全调用。


## Security
- 敏感配置、API Secret、私钥严禁写入 Git 代码库；
- 强保护 `.env` 与私密文件在 `.gitignore` 中被忽视；
- 工具层实施 `ToolPermission` 严格鉴权。

## Testing Strategy
- **Unit & Integration Tests**: 使用 `pytest` 实现全自动绿灯回归测试；
- **Production Gate Tests**: 包含真实 API 对账、反证拦截测试与 100% 断言门控。

## Deployment
- 本地 Python venv 开发与命令行自动化运行；
- Streamlit Cloud 全自动化 Git 推送集成部署。

## Known Technical Constraints
- A 股实时行情依赖第三方 API 连通性，当网络抖动时需准确抛出 `SOURCE_ERROR` / `DATA_UNAVAILABLE`；
- Python 3.9 运行环境下部分 urllib3 警告已通过结构化捕获做无害忽略。

## Architecture Decisions
- 所有架构决策必须在 `DECISIONS.md` 中记录并由 CEO / Founder 最终批准。
