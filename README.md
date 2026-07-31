# A股量化研究系统 (ashare-quant) - 第一阶段 MVP

这是一个极简、轻量且 100% 开源免费的 A 股量化研究系统（MVP 第一阶段）。系统基于 Python 3.10+ 构建，无需任何数据库、付费 API Key、云账号或 Token 注册。

---

## 📁 项目目录结构

```text
ashare-quant/
├── data/                  # 本地 Parquet 数据缓存与结果输出
│   ├── 600519.parquet     # 贵州茅台前复权日线数据
│   ├── stocks_daily.parquet # 10 只成分股汇总数据
│   └── equity_curve_600519.png # 策略净值对比曲线图
├── src/
│   ├── __init__.py
│   ├── data_fetch.py      # 数据获取脚本（基于 akshare）
│   ├── data_quality.py    # 数据质量检查与报告生成
│   ├── backtest.py        # 基于 Pandas 的向量化回测引擎
│   └── strategy/
│       ├── __init__.py
│       └── ma_cross.py    # 双均线交叉策略（5日穿10日）
├── tests/
│   └── test_quant.py      # 单元测试（校验计算与防未来函数逻辑）
├── requirements.txt       # 项目依赖
├── .gitignore             # Git 忽略配置
└── README.md              # 说明文档
```

---

## 🛠️ 环境准备与快速上手

### 1. 克隆与搭建虚拟环境

```bash
# 1.1 进入项目目录
cd ashare-quant

# 1.2 创建虚拟环境 (venv)
python3 -m venv venv

# 1.3 激活虚拟环境
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 1.4 安装项目依赖
pip install -r requirements.txt
```

---

## 🚀 运行流程（4 步跑通全流程）

### 2. 步骤一：一键拉取 A 股前复权日线数据

使用 `akshare` 抓取沪深300精选 10 只成分股近 3 年（2023 ~ 2026）的前复权日线数据，并保存至本地 `data/*.parquet`：

```bash
python src/data_fetch.py
```

### 3. 步骤二：数据质量审计

检查本地 Parquet 数据中是否存在 NaN 缺失值、价格异常或停牌缺口，输出诊断报告：

```bash
python src/data_quality.py
```

*预期输出样例：*
```text
  股票代码 股票名称       起始日期       结束日期  总交易日数  缺失值数量  异常价格数  零成交日数  长停牌缺口数
000001 平安银行 2023-01-03 2025-12-31    727      0      0      0       2
600519 贵州茅台 2023-01-03 2025-12-31    727      0      0      0       2
...
✅ 数据质量优秀：未发现任何字段缺失或价格异常值。
```

### 4. 步骤三：运行双均线策略回测

运行基于 Pandas 向量化计算的双均线策略（5日均线金叉10日均线），输出总收益率、最大回撤、夏普比率并自动保存净值曲线图：

```bash
python src/backtest.py
```

*预期输出样例：*
```text
==================================================
 🚀 策略回测报告: 贵州茅台 (600519) 🚀 
==================================================
  • 初始资金: 100000.0
  • 最终资产: 81985.56
  • 策略总收益率: -18.01%
  • 基准(买入持有)收益率: -12.11%
  • 最大回撤: 19.48%
  • 夏普比率: -0.39
  • 总交易日数: 727
==================================================
📈 净值曲线图已保存至: data/equity_curve_600519.png
```

### 5. 步骤四：运行单元测试

使用 `pytest` 自动化测试信号生成与 `.shift(1)` 防未来函数逻辑：

```bash
pytest tests/
```

---

## 🛡️ 量化设计说明：防未来函数 (Lookahead Bias)

本系统在 `src/backtest.py` 的向量化回测实现中，明确使用了 `.shift(1)`：

```python
# T 日收盘后计算出的信号 signal[T]，最快只能在 T+1 日执行持仓 position[T+1]
data['position'] = data['signal'].shift(1).fillna(0.0)

# T+1 日策略收益 = T+1 日持仓 * T+1 日标的收益率
data['strategy_return'] = data['position'] * data['asset_return']
```

这样确保了回测在计算 T+1 日收益时，绝不提前使用 T+1 日的收盘价，彻底规避未来函数。
