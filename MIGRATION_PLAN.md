# 🏛️ Phase 16 — Vibe-Trading Architecture Integration & Migration Plan

**Document Version**: 1.0.0  
**Project**: AI Quant Pro (`ashare-quant`)  
**Target Architecture**: AI-Powered A-Share Quantitative Research Terminal  
**Upstream Reference**: [HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading)  

---

## 1. 核心迁移原则 (Core Migration Directives)

本迁移方案的核心原则是：**能力提升（Agent Architecture + Tool Registry + Skills + Alpha Zoo + Evidence Lineage），而非破坏覆盖（Preserve Data Integrity & Research Contracts）**。

### 🚨 绝对禁止覆盖与破坏的核心资产 (Strictly Forbidden List)

以下现存于 `ashare-quant` 的核心架构属于防范数据污染、保证 PIT（Point-In-Time）与消除未来函数的基石，**绝对禁止被 Vibe-Trading 代码覆盖或替换**：

1. **PIT Fundamental Data Layer**: `src/data/pit_provider.py` (包含 Publish Date 严格防未来函数机制)
2. **Data Lineage & Contract Engine**: `src/data/contract.py` (`MarketDataContract`, `normalize_market_data_contract`)
3. **Portfolio Contract Engine**: `src/portfolio/contract.py` (`PortfolioSummaryContract`, `normalize_portfolio_summary`)
4. **Research Data Integrity Gate**: `src/system/integrity_gate.py` (`ResearchDataIntegrityGate`, `ResearchDataIntegrityError`)
5. **Canonical Symbol Namespace**: `src/data/symbol_utils.py` (强隔离 `000001.SH` 上证指数 vs `000001.SZ` 平安银行)
6. **Mode Isolation Guard**: Research Mode (真实 API $\rightarrow$ 本地 Parquet $\rightarrow$ `DATA_UNAVAILABLE`) 与 Demo Mode (`DemoMarketDataProvider`) 严格隔离
7. **Zero-Mock Policy in Research Mode**: 真实 API 失败强抛 `DATA_UNAVAILABLE` / `N/A`，严禁产生硬编码数字 (`3280.50`, `3832.26`, `11.50`, `10.00`)
8. **Statistical & Risk Engine**: Walk-Forward OOS Validation (`walk_forward.py`), Bootstrap Significance (`significance.py`), Barra Risk Exposure (`exposure.py`), Portfolio Stress Test (`stress_test.py`)
9. **Evidence & Reproducibility Layer**: `src/experiments/reproducibility.py` (`ResearchReproducibilityRunner`), `DATA_PROVENANCE_AUDIT.md`, `DATA_INTEGRITY_AUDIT.md`
10. **Existing Pytest Suite**: 全量 182 个 Pytest 单元与集成测试必须 100% 保持 GREEN。

---

## 2. 模块结构审计与映射 (Architecture Audit & Mapping)

### 2.1 Vibe-Trading 模块结构分析

```text
Vibe-Trading/
├── agent/src/
│   ├── agent/            # ReAct Agent loop, prompt manager, memory context
│   ├── session/          # Research session, conversation context, state machine
│   ├── providers/        # Multi-LLM provider abstraction (OpenAI, Anthropic, Ollama)
│   ├── skills/           # Skill loader, dynamic skill execution, prompt templates
│   ├── tools/            # Agent tool registry, docstring parser, schema generator
│   ├── memory/           # Persistent research memory, vector/JSON store
│   ├── backtest/         # Vectorized & Event-driven backtest wrappers
│   └── alpha_zoo/        # 452 Alphas (qlib158, alpha101, gtja191, academic)
├── backtest/             # Qlib / Backtrader engine adapters
└── ui/                   # Web interface & Fast API endpoints
```

### 2.2 ashare-quant 当前模块结构

```text
ashare-quant/
├── src/
│   ├── data/             # AkShare, LocalCache, SymbolUtils, Contract, Validation, IntegrityGate
│   ├── factors/          # Momentum, Value, Quality, Volatility, Neutralizer, Analytics
│   ├── strategy/         # Signal, MACross, MultiFactor, RiskEngine, WalkForward, Robustness
│   ├── risk_model/       # Barra Exposure, Risk Decomposition, Stress Test
│   ├── portfolio/        # Portfolio Engine v2, Optimizer, Accounting, Contract
│   ├── execution/        # Costs, PaperTrader, FutuTrader
│   ├── ai/               # AI Analyst, Diagnostics, News Analyzer, LLM Provider
│   ├── experiments/      # Registry, Reproducibility Engine
│   └── services/         # Research, Backtest, Portfolio, ML, AI Services
└── app.py                # Streamlit Product Web Terminal
```

### 2.3 模块映射与迁移决策 (Module Mapping & Migration Table)

| Vibe-Trading 模块 | ashare-quant 目标模块 | 迁移决策 (Migration Decision) | 整合方式 (Integration Method) |
| :--- | :--- | :---: | :--- |
| `agent/src/agent/` | `src/research/agent/` | **迁移并重构** | 实现支持 Tool Call 与 Task Decomposition 的 ReAct Research Agent |
| `agent/src/tools/` | `src/research/tools/` | **新建 Adapter** | 建立 `AgentToolRegistry`，封装现有 Service/IntegrityGate 为安全工具 |
| `agent/src/skills/` | `src/research/skills/` | **迁移并适配** | 迁移因子研究、策略归因、风险审计技能 Prompt 与 Workflow 指引 |
| `agent/src/session/` | `src/research/planner/` | **新建** | 建立 `ResearchPlanner`，解析自然语言需求为 JSON `ResearchPlan` |
| `agent/src/memory/` | `src/research/memory/` | **迁移扩展** | 建立 `ResearchRunCard` 与 Persistent Research Memory |
| `agent/alpha_zoo/` | `src/factors/alpha_zoo/` | **筛选重写** | 筛选防未来函数、符合 A 股机制的 Alpha (Alpha101/Qlib158/GTJA191) 并建立 `AlphaRegistry` |
| `agent/backtest/` | `src/backtest/` | **适配器模式** | 保留 `ashare-quant` 现有回测引擎，建立 `VibeBacktestAdapter` |
| `agent/src/providers/` | `src/ai/llm_provider.py` | **保持现状** | 使用现有的 LLMProvider 接口，不重复造轮子 |

---

## 3. 目标架构设计 (Target Architecture Blueprint)

迁移整合后的 `ashare-quant` 标准目录规范：

```text
ashare-quant/src/
├── data/
│   ├── akshare_provider.py
│   ├── demo_provider.py
│   ├── pit_provider.py
│   ├── cache.py
│   ├── symbol_utils.py       # Canonical Symbol Registry (000001.SH vs 000001.SZ)
│   ├── contract.py           # MarketDataContract & Normalization
│   └── integrity_gate.py     # ResearchDataIntegrityGate (防数据污染)
│
├── factors/
│   ├── factor_engine.py
│   ├── analytics.py
│   ├── neutralizer.py
│   └── alpha_zoo/            # [NEW] Alpha 因子工场
│       ├── registry.py       # AlphaRegistry & AST Standardizer
│       ├── alpha101.py       # Kakushadze 101 Formulated Alphas (A-Share Safe)
│       ├── qlib158.py        # Qlib 158 Cross-Sectional Features
│       └── gtja191.py        # Guotai Junan 191 Factors
│
├── research/                 # [NEW] AI Research Agent Framework
│   ├── agent/
│   │   ├── react_agent.py    # Multi-step Reasoning & Action Loop
│   │   └── prompts.py        # Quant Research System Prompts
│   ├── tools/
│   │   ├── registry.py       # AgentToolRegistry
│   │   ├── market_tools.py   # Integrated with IntegrityGate
│   │   ├── factor_tools.py   # IC/IR/Decay/AlphaZoo Tools
│   │   ├── backtest_tools.py # Backtest & WalkForward Tools
│   │   └── risk_tools.py     # Barra Risk & Stress Test Tools
│   ├── planner/
│   │   ├── planner.py        # Natural Language -> ResearchPlan JSON
│   │   └── schema.py         # ResearchPlan Data Schema
│   ├── memory/
│   │   ├── run_card.py       # ResearchRunCard & Lineage Metadata
│   │   └── store.py          # Persistent Research Memory Store
│   ├── skills/
│   │   ├── factor_research.md
│   │   ├── alpha_bench.md
│   │   └── risk_attribution.md
│   └── reports/
│       └── evidence_report.py# Evidence-Grounded AI Research Report Generator
│
├── backtest/                 # Backtest Engine & Vibe Adapter
│   ├── engine.py
│   └── vibe_adapter.py       # Adapter for Vibe-Trading backtest calls
│
├── risk_model/               # Barra Risk & Stress Testing
├── portfolio/                # Portfolio Management & PortfolioSummaryContract
├── execution/                # Transaction Costs & Execution
├── services/                 # Service Layer Protocols
└── ui/                       # Streamlit App Panels
```

---

## 4. 关键组件整合机制 (Key Component Specifications)

### 4.1 Research Agent 与 Data Integrity Gate 强关联机制

Agent **绝对不允许直接调取裸 Dataframe 或绕过数据校验**。所有 Agent Tool 的执行链路：

```text
[AI Research Agent]
         ↓ (Call Tool)
[Agent Tool Registry]
         ↓ (Validate Tool Input Schema)
[Research Tool Implementation]
         ↓
[ResearchDataIntegrityGate.assert_valid_research_data()]
         ↓
[MarketDataContract / Service Layer]
         ↓
[Real Market Data / Real Cache]  --> (API 失败) --> [DATA_UNAVAILABLE Error]
         ↓ (Return Verified Evidence)
[AI Agent Memory & Evidence Lineage]
```

### 4.2 Alpha Zoo 机制与未来函数审计

迁移进入 `src/factors/alpha_zoo/` 的每一个 Alpha 公式必须通过以下 5 维断言测试：

1. **AST / Purity Check**: 确认无动态全局变量修改
2. **Look-Ahead Bias Test**: 确认计算只依赖 `t <= T` 历史切片，不使用未来收盘价或未来财报发布
3. **NaN & Div-Zero Protection**: 确认具备除零防护与填充机制
4. **Cross-Sectional Normalization**: 自动通过 Z-Score / Rank 进行截面标准化
5. **Canonical Symbol Compliance**: 强制使用 `000001.SH` / `600519.SH` 等带后缀代码

### 4.3 Research Planner 自然语言解析架构

解析用户输入（如 *"研究一下过去五年 A 股动量因子在沪深 300 中的有效性"*）为结构化 JSON：

```json
{
  "query": "研究过去五年 A 股动量因子在沪深 300 中的有效性",
  "universe": ["000300.SH"],
  "canonical_symbols": ["600519.SH", "000001.SZ", "300750.SZ", "601899.SH"],
  "start_date": "2021-01-01",
  "end_date": "2026-07-31",
  "factors": ["Momentum_20D", "Alpha_101_006"],
  "forward_horizons": [1, 5, 10, 20],
  "transaction_cost": true,
  "neutralization": true,
  "walk_forward": true,
  "risk_model": "Barra_SW_Industry",
  "statistical_test": "Bootstrap_95CI"
}
```

---

## 5. 开源许可证与版权审计 (License & Attribution Audit)

### 5.1 项目许可证兼容性

- **Vibe-Trading 开源许可**: **MIT License** (允许商业使用、修改、分发、私有化使用)
- **ashare-quant 开源许可**: **MIT / Proprietary Project**
- **结论**: 许可证完全兼容。

### 5.2 第三方组件及 Alpha 因子版权审计矩阵

| 组件 / 因子集 | 原始来源 (Original Source) | 原始许可证 (License) | 迁移决策 (Decision) | Attribution 声明要求 |
| :--- | :--- | :--- | :--- | :--- |
| **Agent / Tool Registry 架构** | HKUDS/Vibe-Trading | MIT | 重新设计适配当前 Service 层 | 保留 Vibe-Trading 架构参考致谢 |
| **Alpha101 (Formulaic Alphas)** | Zura Kakushadze (101 Formulaic Alphas) | Public Domain / Academic | 基于 Python/Pandas 重构数学表达 | 在代码 Docstring 标注公开发表论文引用 |
| **Qlib158 (Feature Set)** | Microsoft Qlib | MIT | 引入 A 股适配切片版 | 标注 Source: Microsoft Qlib (MIT) |
| **GTJA191 (Short-Period Alphas)** | 国泰君安证券研报 | Academic / Financial Research | 重新实现算子并添加 PIT 检验 | 标注 Source: GTJA Quantitative Research |
| **Academic Factors (Fama-French)** | Fama & French (1993/2015) | Academic | 重新根据 A 股财务数据重写 | 标注 Academic Reference |

---

## 6. 依赖项与环境冲突分析 (Dependency Conflicts Audit)

| 依赖库 (Package) | Vibe-Trading 版本 | ashare-quant 当前版本 | 冲突评估 & 统一决策 |
| :--- | :--- | :--- | :--- |
| **Python** | 3.10+ | **3.9.6** | 保持 3.9.6 兼容性（使用 `typing.Dict`, `Optional` 代替 `dict[str, str]` 3.10+ 语法） |
| **Pandas** | >= 2.0.0 | **2.2.3** | 完全兼容 |
| **Numpy** | >= 1.24.0 | **1.26.4** | 完全兼容 |
| **AkShare** | 最新 | **最新** | 完全兼容 |
| **Streamlit** | N/A (使用 Next.js) | **1.41.1** | **保留 Streamlit**，在 `app.py` 中新增 `🧠 AI Research Agent` 独立 Tab |
| **Vectorbt / PyPfolio** | 可选 | **可选/现有算法** | 优先使用现有的 Backtest Service |

---

## 7. 8-Commit 分阶段实施路线图 (Step-by-Step Execution Plan)

为确保整个过程无回归错误、测试 100% 保持 GREEN，实施划分为 8 个独立的 Git Commit：

```text
[Commit 1: Architecture Audit & Migration Plan] (当前步骤 - 仅产出 MIGRATION_PLAN.md)
       ↓
[Commit 2: Alpha Zoo & AlphaRegistry]
  └─ 创建 src/factors/alpha_zoo/ (Alpha101/Qlib158/GTJA191，通过 AST & Lookahead 测试)
       ↓
[Commit 3: Agent Tool Registry & Integrity Tools]
  └─ 创建 src/research/tools/ (12 个必须通过 ResearchDataIntegrityGate 的工具)
       ↓
[Commit 4: Research Planner & Plan Schema]
  └─ 创建 src/research/planner/ (自然语言 -> 结构化 ResearchPlan)
       ↓
[Commit 5: ReAct Agent Framework & Skills]
  └─ 创建 src/research/agent/ & src/research/skills/ (多步推理与量化技能)
       ↓
[Commit 6: Research Run Cards & Evidence Traceability]
  └─ 创建 src/research/memory/ & src/research/reports/ (实验卡片与全血缘报告)
       ↓
[Commit 7: UI Integration (🧠 AI Research Agent Panel)]
  └─ 更新 app.py，新增 AI Quant Research 交互面板
       ↓
[Commit 8: Comprehensive Regression Test Suite]
  └─ 新增 11 个 Phase 16 专属 Agent/Tool/Alpha 测试，确保全量 Pytest 100% GREEN
```

---

## 8. 当前阶段完成标志 (Phase 16 Step 1 Completion Criteria)

1. ✅ 深入审计 Vibe-Trading 与 ashare-quant 架构
2. ✅ 建立完整 `MIGRATION_PLAN.md` 规范文档
3. ✅ 完成 License、依赖冲突与 Alpha 因子版权审查
4. 🛑 **暂停下一步代码修改，等待用户审查并确认 `MIGRATION_PLAN.md`。**
