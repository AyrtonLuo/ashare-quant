# Product Definition

## Product Vision
AI Quant Pro (`ashare-quant`) 旨在打造一个高确定性、符合 A 股市场特性的开源 AI 量化研究与交易平台。集成成熟的 AI Research Agent、Factor Engine、PIT 基础面库、Alpha Zoo、Walk-Forward 回测引擎与全数据血缘存证机制，为量化研究员与个人投资者提供机构级的全闭环量化基础设施。

## Target Users
1. A 股量化研究员与因子开发员；
2. 追求 PIT 安全与严密 Look-Ahead 校验的 AI 量化对冲投资者；
3. 需要自动化 AI ReAct Agent 协助进行多因子归因与风控压力测试的专业交易员。

## Core Problem
1. **未来函数与 PIT 数据泄露**: 传统回测系统常因未披露财报提前计入或行情全复权偏误导致回测虚高；
2. **数据污染与假数据降级**: 部分 AI 量化平台在 API 失效时隐蔽使用 `fillna(0)`、Mock 假价格或伪造数据降级；
3. **Agent 越权与不透明**: AI Agent 缺乏工具权限门控，直接访问底层 Parquet 或网络接口导致归因不可追溯；
4. **命名空间与代码歧义**: A 股代码如 `000001` 在指数 (上证指数 000001.SH) 与股票 (平安银行 000001.SZ) 之间存在严重歧义。

## Core Value Proposition
1. **100% Canonical Symbol & Namespace Isolation**: 强隔离 `000001.SH` (上证指数) 与 `000001.SZ` (平安银行)，全库无裸代码；
2. **Zero-Fallback Data Integrity**: 真实 Research Mode 强拒绝 Demo/Mock/假行情；API 异常返回 `DATA_UNAVAILABLE`，绝不到 `0` 隐蔽覆盖；
3. **Agent Tool Registry Boundary**: Agent 100% 经过 `AgentToolRegistry` 鉴权与执行，保留全血缘 SHA-256 存证；
4. **PIT & Look-Ahead Safety**: 自动化财报发布日 `publication_date <= trading_date` 切片校验。

## Core Features
1. **Market Data & Contract Layer**: 规范化 `MarketDataContract`, `HistoricalMarketDataContract`, `FundamentalDataContract`；
2. **Alpha Zoo & Factor Engine**: 支持 `MOM_20D`, `VOL_20D`, `TURNOVER_20D`, `EP_TTM` 等标准因子算子；
3. **ReAct Research Agent & Planner**: 确定性规划器 `ResearchPlanner` 与受控 `ReActResearchAgent`；
4. **Research Evidence Layer**: 自动化生成包含哈希防篡改卡片的 `ResearchResult`；
5. **Streamlit Web UI Terminal**: 极简极炫的双模式 (Research / Demo) 交互终端。

## Non-Goals
1. **不追求美股/加密货币等多市场混用**: 专注于 A 股 (SH/SZ/BJ) 的特定交易规则、涨跌停限制与 PIT 披露标准；
2. **不搞黑盒无隐患 UI 盖面**: 拒绝任何在 UI 层简单 try/except 遮蔽底座算子报错的做法。

## Product Principles
1. **Data Accuracy Over Availability**: 宁可标记 `DATA_UNAVAILABLE`，也绝对不展示伪造的价格与估计值；
2. **Single Source of Truth**: 接口、符号、单位、时间戳在底座 Adapter 统一归一化，禁止上层各自为政；
3. **Reproducibility & Lineage**: 任何量化研究结论必须具备 100% 可追溯的存证卡片与 Hash。
