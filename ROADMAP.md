# Roadmap

## Phase 0 — Foundation & Data Contracts
- Status: **COMPLETED**
- Scope: MarketDataContract, Research/Demo Mode 隔离, Canonical Symbol System (`000001.SH` vs `000001.SZ`), ResearchDataIntegrityGate, PIT Basic Protection.

## Phase 16 Step 1 — Migration Architecture Plan
- Status: **COMPLETED**
- Scope: 完成与开源 Vibe-Trading 的架构映射并建立 `MIGRATION_PLAN.md`。

## Phase 16 Step 2 & 2.5 — Alpha Zoo & Real Data Validation Gate
- Status: **COMPLETED**
- Scope: 建立 `AlphaRegistry` 与 Alpha Zoo (MOM, REV, VOL, TURNOVER, EP_TTM)，并通过 5 大真实标的 Production Gate 验证。

## Phase 16 Step 3 — Agent Tool Registry & Integrity Tools
- Status: **COMPLETED**
- Scope: 建立 18 个 Approved Agent Tools, `AgentToolRegistry`, `ToolPermission` 鉴权与 `ToolExecutionRecord` 存证。

## Phase 16 Step 4 & 4.5 — ReAct Agent & Production Gate
- Status: **COMPLETED**
- Scope: 建立 `ResearchPlanner` 与 `ReActResearchAgent`，通过 6 大反证拦截测试与 259 项 100% 绿灯回归测试。

## Phase 16 Step 4.6 — API Alignment & Unified Data Contract
- Status: **COMPLETED**
- Scope: 建立全库 API Inventory, `FundamentalDataContract`, `MLFeatureContract`, `PredictionContract`, `ErrorStatus` 与 `API_ALIGNMENT_SPEC.md`。

## Phase 16 Step 4.7 — Numerical Truth & Cross-API Validation
- Status: **COMPLETED**
- Scope: 新增 `HistoricalMarketDataContract`，完成 4 大因子手动数学公式对齐，清除伪造 fallback，落盘 `PHASE16_STEP4_7_NUMERICAL_TRUTH_AUDIT.md`。

## Phase 16 Step 4.8 — External API Truth Audit & Production Reconciliation
- Status: **COMPLETED**
- Scope: 完成外部真实 API 动态核对、双源交叉验证、Symbol 强隔离、单位标准化、ML 得分零假数据归因，落盘 `PHASE16_STEP4_8_EXTERNAL_TRUTH_AUDIT.md` (303 测试 100% 绿灯)。

## Phase 16 Step 4.9 — CEO ↔ CTO Collaboration Operating System Setup
- Status: **IN_PROGRESS**
- Scope: 建立 CEO (ChatGPT) ↔ CTO (Antigravity) 协作基础设施与共享项目记忆库 (`PRODUCT.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `DECISIONS.md`, `STATUS.md`, `communication/`, `tasks/`, `.agents/rules/cto.md`)。

## Phase 16 Step 5 — Multi-Agent Swarm / Agent UI / Research Memory System
- Status: **PAUSED / PENDING CEO APPROVAL**
- Scope: 组装 FastAPI / MCP / Web UI 交互及 Swarm 多 Agent 协作系统。
