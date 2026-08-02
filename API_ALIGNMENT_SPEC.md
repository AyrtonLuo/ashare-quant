# 📐 Phase 16 Step 4.6 — Unified API Alignment & Data Contract Specification

**Document Version**: 1.0.0  
**Project**: AI Quant Pro (`ashare-quant`)  
**Phase Objective**: 将全库行情、基本面、指数、历史数据、因子、ML 与 Research API 进行完整对齐，建立 Single Source of Truth 契约，彻底消除 `fillna(0)`、KeyError、字段命名歧义与 000001 命名空间混乱。  

---

## 1. 核心架构与设计原则 (Core Principles)

1. **先统一 API，再统一数据，再统一 Alpha，最后才继续 Agent**；
2. **Canonical Symbol 强制标准化**: 全平台内部仅接受 `600519.SH`, `000001.SZ`, `000001.SH`, `000300.SH`, `688110.SH` 格式，裸代码（如 `000001`）被严格阻断；
3. **零假数据补零原则 (Zero-Fallback to 0)**: 严禁将 `None` / `NaN` / 异常静默转化为 `0`。`0` 仅代表真实的量化数值 0，数据缺失或异常必须标记为 `DATA_UNAVAILABLE` 或 `DATA_INSUFFICIENT`；
4. **Adapter 层归一化**: 第三方字段（如 AkShare `pct_chg` / Tencent `price`）仅在底层 Adapter 转换为统一契约 `MarketDataContract` / `FundamentalDataContract`，绝不上漏污染 Service / Agent / UI 层。

---

## 2. 统一数据契约汇总 (Unified Data Contracts)

### 2.1 MarketDataContract (行情契约)
| 字段 (Field) | 类型 (Type) | 单位/格式 (Unit/Format) | 说明 (Description) |
| :--- | :--- | :--- | :--- |
| `symbol` | `str` | `Canonical (e.g. 600519.SH)` | 统一标准 A 股/指数代码 |
| `name` | `str` | `UTF-8 String` | 标的名称 (e.g. 贵州茅台 / 上证指数) |
| `market` | `str` | `SH / SZ / BJ` | 所属交易所 |
| `timestamp` | `str` | `YYYY-MM-DD HH:MM:SS` | 报价生成时间戳 (Asia/Shanghai) |
| `open` | `Optional[float]` | `RMB` | 开盘价 |
| `high` | `Optional[float]` | `RMB` | 最高价 |
| `low` | `Optional[float]` | `RMB` | 最低价 |
| `close` | `Optional[float]` | `RMB` | 最新收盘价 / 现价 |
| `volume` | `float` | `Shares` | 股数成交量 |
| `amount` | `float` | `RMB` | 成交金额 |
| `change_pct` | `float` | `Ratio (e.g. 0.025 代表 +2.5%)` | 涨跌幅比例 |
| `status` | `str` | `ErrorStatus` | 状态 (`AVAILABLE` / `DATA_UNAVAILABLE`) |
| `source` | `str` | `String` | 真实数据源 (e.g. `AkShare Spot API` / `Tencent Realtime API`) |
| `data_mode` | `str` | `RESEARCH` | 数据隔离模式 (`RESEARCH` / `DEMO`) |
| `is_real` | `bool` | `True / False` | 真实数据标记 |

### 2.2 FundamentalDataContract (PIT 基本面契约)
| 字段 (Field) | 类型 (Type) | 单位/格式 (Unit/Format) | 说明 (Description) |
| :--- | :--- | :--- | :--- |
| `symbol` | `str` | `Canonical` | 规范代码 |
| `trading_date` | `str` | `YYYY-MM-DD` | 切片交易日 |
| `fiscal_period` | `str` | `YYYYQ1-Q4` | 财报报告期 |
| `publication_date` | `str` | `YYYY-MM-DD` | 财报真实公开披露日 (PIT Cutoff) |
| `effective_date` | `str` | `YYYY-MM-DD` | 生效公开日 |
| `pe_ttm` | `Optional[float]` | `Ratio` | 滚动市盈率 |
| `pb` | `Optional[float]` | `Ratio` | 市净率 |
| `roe` | `Optional[float]` | `Ratio (e.g. 0.27 代表 27%)` | 净资产收益率 |
| `eps` | `Optional[float]` | `RMB` | 每股收益 |
| `revenue` | `Optional[float]` | `RMB` | 营业收入 |
| `net_profit` | `Optional[float]` | `RMB` | 净利润 |
| `status` | `str` | `ErrorStatus` | PIT 状态 (`AVAILABLE` / `PIT_REJECTED` / `DATA_UNAVAILABLE`) |

---

## 3. 全库 API Inventory & Matrix

| API 名称 | 文件路径 | 函数/方法 | 输入格式 | 输出契约 | PIT 约束 | 错误行为 |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| `get_latest` | `src/data/provider.py` | `MarketDataProvider.get_latest` | `symbol: Canonical` | `MarketDataContract` | N/A | 返回 `status="UNAVAILABLE"` |
| `get_hist` | `src/data/provider.py` | `MarketDataProvider.get_hist` | `symbol, start, end` | `pd.DataFrame` | Clean Cutoff | 返回空 DataFrame |
| `get_pit_fundamental` | `src/data/pit_provider.py` | `PITFundamentalProvider.get_pit_fundamental` | `symbol, trading_date` | `FundamentalDataContract` | `pub <= trade` | 返回 `status="PIT_REJECTED"` |
| `compute` | `src/factors/alpha_zoo.py` | `Alpha.compute` | `data: pd.DataFrame` | `AlphaEvidenceRecord` | 21D Window | 返回 `status="DATA_INSUFFICIENT"` |
| `execute` | `src/research/tools/registry.py` | `AgentToolRegistry.execute` | `tool_name, context, kwargs` | `ToolResult` | Context Safe | 返回 `success=False, error=...` |

---

## 4. 688110.SH (东方生物) 数据链 Before / After 架构对比

```text
BEFORE (修复前):
Raw API (AkShare / Tencent)
   ↓ (返回 {'price': 34.2, 'code': '688110'})
Upper Code / Service
   ↓ (上层代码分别尝试 raw.get("price"), raw.get("close"), raw.get("latest_price"))
   ↓ (KeyError 或 AttributeError 频发，或 fillna(0) 导致假行情 0)
UI / Agent
   ↓ (呈现错误或者隐蔽的假 0 数值)

AFTER (统一 API 对齐后):
Raw API (AkShare / Tencent)
   ↓
Provider Adapter Layer (src/data/contract.py: normalize_market_data_contract)
   ↓ (使用 _safe_get & _safe_float 归一化为 MarketDataContract)
MarketDataContract (symbol="688110.SH", close=34.2, status="AVAILABLE", source="Tencent", is_real=True)
   ↓
ResearchDataIntegrityGate (防线校验 symbol, status, is_real)
   ↓
Service Layer (get_services)
   ↓
Agent Tool Registry (AgentToolRegistry.execute("get_market_quote"))
   ↓
ReActResearchAgent / ResearchResult
   ↓
Streamlit Cloud UI (100% 结构化呈现，零 KeyError，零假数据)
```

---

## 5. 零假数据审计总结 (Zero-Fallback Audit)

- **`fillna(0)` 审计**: 仅在构建已知收益率差值矩阵矩阵且列已校验齐全时保留；所有行情/估值/基本面接口禁止任何 `fillna(0)` 隐蔽覆盖；
- **`return 0` / `except Exception` 审计**: 捕获异常后统一构造 `status="DATA_UNAVAILABLE"`, `close=None` 的 Contract 实例，完全杜绝了 API 异常返回 0 股价破坏量化因子的严重隐患。

---

## 6. 测试验证汇总 (Test Verification)

- **新增 API 对齐测试文件**: [tests/test_api_alignment.py](file:///Users/yuhanluo/ashare-quant/tests/test_api_alignment.py) (18 项测试)
- **全量 Pytest 汇总**: **259 Passed, 0 Failed, 100% GREEN** (耗时 9.94 秒)
- **Git Branch**: `main`
- **Git Commit Hash**: `c277c7f` (与后续最新提交)
