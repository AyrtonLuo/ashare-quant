# Ashare Quant Pro 专业化路线

## 产品定位

Ashare Quant Pro 目标是从当前的 A 股量化研究 MVP，升级为一套面向个人研究者、小型投研团队和模拟交易场景的专业量化工作台。核心价值不是给出单一买卖建议，而是把数据、研究、风控、组合构建、模拟执行和复盘沉淀成一条可审计的工作流。

## 当前基础

- 数据层：Data Layer 2.0 (MarketData 模型、MarketDataProvider 抽象、AkShareProvider、FutuProvider、LocalCache Parquet 缓存、HistoricalUniverseProvider).
- 因子层：Factor Engine (Factor 抽象、Momentum, Value, Quality, Volatility, Liquidity, MAD 去极值、Z-Score 标准化、行业/市值中性化).
- 研究层：MultiFactorStrategy、Composite Alpha 权重合成、实验注册表 ExperimentRegistry (Git Commit 关联、配置落盘).
- 回测层：BacktestEngine2 统一架构、SlicedMarketDataProvider 防未来函数数据切片、VectorBT/Pandas 100% 撮合一致性.
- 组合与执行层：Portfolio Engine 2.0 (Position, Order, OrderSide/OrderStatus, ExecutionEngine, TransactionCostModel, PortfolioAccounting, PaperAccount Facade).
- 控制台与报告：Streamlit 🧪 Strategy Lab、DecisionAuditLog Markdown 决策审计日志 (reports/YYYY-MM-DD_rebalance.md).



## 专业软件标准

1. 数据可信
   - 行情源、缓存源、降级源必须明确标记。
   - 所有策略计算必须避免未来函数。
   - 每次调仓需要记录使用的数据时间、价格来源和风控状态。

2. 研究可复现
   - 因子计算、预处理、IC、分层回测和组合生成参数可配置。
   - 每个研究结果应能落盘，方便横向对比。
   - 核心研究模块必须有离线单元测试。

3. 风控先于收益
   - 组合总仓位、单股权重、交易批量、现金保留和熔断规则要统一入口。
   - 模拟盘和回测必须共享关键交易假设。
   - 所有自动调仓都先生成预演，再执行模拟撮合。

4. 执行可审计
   - 订单、成交、费用、冻结股份和现金变动要可追踪。
   - UI 展示价格与撮合价格必须同源。
   - 每次运行应能区分真实行情、本地缓存和 fallback 价格。

5. 产品可演示
   - 第一屏必须展示账户、仓位、风险状态和行情来源。
   - 研究、调仓、持仓、情报分区清晰。
   - 默认流程能在无付费 API 的环境下完成演示。

## 三阶段路线

### 阶段 1：专业工作台

- 重构 Streamlit 信息架构：总览、调仓、持仓、情报。
- 引入行情缓存与本地价格降级，减少实时接口重复调用。
- 修正模拟撮合价格口径，保证 UI 最新价与交易引擎一致。
- 固化模拟盘价格解析测试。

### 阶段 2：研究生产化

- 把因子研究参数抽到配置文件。
- 增加研究结果 registry：每次 IC、分层回测、组合权重和风险报告落盘。
- 增加离线 demo dataset，CI 可以不依赖 AkShare 网络。
- 给回测、模拟盘、风控增加统一交易假设对象。

### 阶段 3：准实盘工作流

- 增加日内任务调度：开盘前数据更新、盘中风控检查、收盘后复盘。
- 模拟订单状态机升级为 pending、filled、rejected、cancelled。
- 接入券商接口前增加风控拦截层与人工确认层。
- 增加权限、审计日志和策略版本号，支持团队协作。

## 最近五个高价值任务

1. 把 app.py 中的目标组合编辑结果持久化到 session，并支持导入最新 Top 5% 研究组合。
2. 把 PaperAccount 的交易假设抽成 dataclass，统一手续费、印花税、最小交易单位和 T+1 规则。
3. 将网络型测试与离线核心测试分组，避免外部数据源拖慢本地回归。
4. 为每次调仓输出一份 Markdown/JSON 决策报告，记录行情时间、价格来源、仓位上限和订单。
5. 给 Streamlit 控制台增加只读演示模式，避免公开演示时误重置真实模拟账户。
