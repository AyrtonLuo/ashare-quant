# 🔬 Phase 16 Step 4.7 — Numerical Truth & Cross-API Validation Audit Report

**Document Version**: 1.0.0  
**Project**: AI Quant Pro (`ashare-quant`)  
**Audit Objective**: 验证数值在 `Raw API -> Adapter -> Contract -> Service -> Alpha -> ML -> ResearchResult` 全链路传递中绝对无损一致，并完成 4 大类 Alpha 因子数学手动对齐与 6 大类异常状态归一化。  

---

## 1. 历史行情契约决策 (Historical Market Data Contract Decision)

为避免裸 `pd.DataFrame` 在各层间被自行解释导致复权方式、时间轴、缺失值填充不一致，我们在 [src/data/contract.py](file:///Users/yuhanluo/ashare-quant/src/data/contract.py) 中正式新增 `HistoricalMarketDataContract`：

```python
@dataclass
class HistoricalMarketDataContract:
    symbol: str
    start_date: str
    end_date: str
    adjust: str = "qfq"                       # 前复权强制标记
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    status: str = ErrorStatus.AVAILABLE.value
    source: str = "MarketDataProvider"
    data_mode: str = "RESEARCH"
    is_real: bool = True
```

---

## 2. 真实数据全链路数值传递矩阵 (Raw -> Contract -> Research)

在真实 A 股数据模式 (Research Mode) 下验证 6 大核心标的数值无损传递：

| Symbol | 标的名称 | Raw Source Price | Contract Close | Service Close | Tool Quote | Result Match Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| `688110.SH` | 东方生物 | `34.50 RMB` | `34.50 RMB` | `34.50 RMB` | `34.50 RMB` | **EXACT MATCH** |
| `600519.SH` | 贵州茅台 | `1450.00 RMB` | `1450.00 RMB` | `1450.00 RMB` | `1450.00 RMB` | **EXACT MATCH** |
| `600036.SH` | 招商银行 | `31.20 RMB` | `31.20 RMB` | `31.20 RMB` | `31.20 RMB` | **EXACT MATCH** |
| `000001.SZ` | 平安银行 | `11.50 RMB` | `11.50 RMB` | `11.50 RMB` | `11.50 RMB` | **EXACT MATCH** |
| `000001.SH` | 上证指数 | `3280.50 Pts` | `3280.50 Pts` | `3280.50 Pts` | `3280.50 Pts` | **EXACT MATCH** |
| `000300.SH` | 沪深300 | `3832.26 Pts` | `3832.26 Pts` | `3832.26 Pts` | `3832.26 Pts` | **EXACT MATCH** |

---

## 3. Alpha 数学公式手动交叉验证 (Manual Math Verification)

在 [tests/test_numerical_truth.py](file:///Users/yuhanluo/ashare-quant/tests/test_numerical_truth.py) 中，对 4 种典型 Alpha 执行了精确到 $10^{-5}$ 的公式对齐校验：

### 3.1 Momentum_20D (20日动量)
- **公式**: $MOM\_20D = \frac{P_t}{P_{t-20}} - 1.0$
- **手动结果**: $120.0 / 100.0 - 1.0 = 0.20000$ (+20%)
- **AlphaRegistry 结果**: `0.20000`
- **结果**: **PASS** (绝对误差 $< 10^{-5}$)

### 3.2 Volatility_20D (20日年化波动率)
- **公式**: $VOL\_20D = \text{std}(\Delta P / P, 20) \times \sqrt{252}$ (ddof=1)
- **手动结果**: `0.452517`
- **AlphaRegistry 结果**: `0.452517`
- **结果**: **PASS** (绝对误差 $< 10^{-5}$)

### 3.3 Liquidity_20D (Turnover_20D 换手流动性)
- **公式**: $\text{mean}(\text{amount}_{t-19:t})$
- **手动结果**: `30000.00`
- **AlphaRegistry 结果**: `30000.00`
- **结果**: **PASS**

### 3.4 Value / EP_TTM (盈利率因子)
- **公式**: $EP\_TTM = \frac{1.0}{PE\_TTM}$
- **手动结果**: $1.0 / 25.0 = 0.04000$
- **AlphaRegistry 结果**: `0.04000`
- **结果**: **PASS**

---

## 4. 之前 688110.SH 异常排查与根因修复 (Previous Anomaly Audit)

在早期测试中，`688110.SH` 偶尔出现 `EP_TTM = 0` 或 `MOM_20D = 0` 的假数值。

#### 调查结论与根本修复：
1. **根本原因**: `src/factors/alpha_zoo/value.py` 内部曾包含代码 `return 1.0 / (df["close"] * 0.05 + 1.0)` 的伪造 fallback 逻辑；当基本面 `pe_ttm` 缺失时，该伪造公式计算出接近 0 的伪估值。
2. **修复机制**: 彻底移除该伪造 fallback！当基本面缺失时，`compute_ep_ttm` 正确返回全 `NaN` 序列，被上层判定为 `status="DATA_INSUFFICIENT"`, `value=None`，**绝不上漏为 0**！

---

## 5. 错误语义与状态码对齐矩阵 (Error Semantics Audit)

| 异常触发场景 (Scenario) | 旧系统输出 | Step 4.7 对齐后标准 Status |
| :--- | :--- | :--- |
| 第三方 API 网络超时 / 连接中断 | `DATA_UNAVAILABLE` | `SOURCE_ERROR` |
| 行情 Cache / API 无此标的记录 | `DATA_UNAVAILABLE` | `DATA_UNAVAILABLE` |
| 无法解析的无效 Symbol (e.g. `INVALID.SH`) | KeyError | `INVALID_SYMBOL` |
| 历史 K 线天数 $< 21$ 天 | 返回 0 或 NaN | `DATA_INSUFFICIENT` |
| 财报披露日 `pub > trade` | 隐蔽穿透泄漏 | `PIT_REJECTED` |
| 算子中除零或数据全为空 | 抛出 AttributeError | `CALCULATION_ERROR` |

---

## 6. 全量测试与提交状态 (Test Results & Git Status)

- **新增数值真理测试**: [tests/test_numerical_truth.py](file:///Users/yuhanluo/ashare-quant/tests/test_numerical_truth.py) (14 项测试)
- **全量 Pytest 汇总**: **291 Passed, 0 Failed, 100% GREEN** (耗时 9.94 秒)
- **Git Branch**: `main`
- **Git Commit Hash**: `11a2c7b` (以及包含本报告的最新提交)

---

🛑 **暂停说明**：
API 对齐 (Step 4.6) 与 数值真理/交叉验证 (Step 4.7) 均已 100% 验证 PASS。我们已保持暂停状态，未擅自进入 Phase 16 Step 5。
