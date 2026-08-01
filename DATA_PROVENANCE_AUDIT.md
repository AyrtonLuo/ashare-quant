# 🔍 DATA PROVENANCE & RESEARCH INTEGRITY AUDIT

**Audit Date**: 2026-08-01  
**Auditor**: AntiGravity AI Quant Engineering Team  
**Scope**: Full Repository Hardcoded / Mock / Fixture / Real Research Code Paths

---

## 1. Executive Audit Summary

本文档对系统内部全量数据源、因子计算、回测指标、统计假设检验以及 AI 研报问答模块进行了透明审计，明确标明每一项指标究竟属于 **`REAL RESEARCH RESULT` (真实行情与 PIT 计算结果)** 还是 **`RESEARCH MODEL / STATISTICAL APPROXIMATION` (研究模型理论估算)** 还是 **`DEMO / MOCK DATA` (确定性演示数据)**。

---

## 2. Metric-by-Metric Provenance Matrix

| Metric / Component | Declared Source | Audit Category | Code Path / Module | Can Reproduce | Audit Notes |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **A-Share Daily Quotes (OHLCV)** | AkShare API + Parquet Cache | **REAL RESEARCH RESULT** | `src/data/akshare_provider.py` | **YES** | 真实从网易/新浪/东方财富数据接口获取 |
| **Index Symbol Mapping** | SH/SZ Prefix Standardizer | **REAL RESEARCH RESULT** | `src/data/symbol_utils.py` | **YES** | 修正 `000001.SH` 上证指数 vs `000001.SZ` 平安银行 |
| **PIT Fundamental Data** | Financial Statements + Lag | **REAL RESEARCH RESULT** | `src/data/fundamental/provider.py` | **YES** | 严格基于 `publication_date`，未披露期自动遮蔽 |
| **Factor Matrix Calculation** | FactorEngine (Z-score/MAD) | **REAL RESEARCH RESULT** | `src/factors/factor_engine.py` | **YES** | 动态从截面行情实时计算 EP, Momentum, Vol, Liq |
| **Factor Decay Curve (1D-60D)** | Half-Life Exponential Decay | **RESEARCH MODEL APPROX** | `src/factors/analytics.py` | **YES** | 采用理论半衰期衰减模型估算 $IC(t) = IC_0 e^{-\lambda t}$ |
| **Barra Risk Exposure (6 Style)** | Weighted Portfolio Exposure | **REAL RESEARCH RESULT** | `src/risk_model/exposure.py` | **YES** | 从组合持仓与截面因子值实时加权求和 |
| **Risk Decomposition (Factor/Spec)** | Covariance Matrix Decomposition | **REAL RESEARCH RESULT** | `src/risk_model/decomposition.py` | **YES** | 结合股票日度收益率协方差矩阵实时分解 |
| **Market Impact Model** | Square-Root Law | **RESEARCH MODEL APPROX** | `src/execution/costs.py` | **YES** | 按照 $\text{Impact} \propto \sqrt{\text{OrderSize}/\text{ADV}}$ 公式计算 |
| **Walk-Forward OOS Results** | 5-Fold Rolling OOS Engine | **REAL RESEARCH RESULT** | `src/strategy/walk_forward.py` | **YES** | 自动切分 2018–2026 连续 5 Fold 运行滚动回测 |
| **Bootstrap 95% CI & p-value** | 500 Resamples Bootstrap | **REAL RESEARCH RESULT** | `src/stats/significance.py` | **YES** | 对真实收益序列进行 500 次自采样分布拟合 |
| **Portfolio Stress Testing** | Extreme Shock Simulation | **RESEARCH MODEL APPROX** | `src/risk_model/stress_test.py` | **YES** | 模拟大盘 -10%/-20%/-30% 及流动性减半冲击 |
| **Demo Mode Market Data** | Deterministic Offline Feed | **DEMO / MOCK DATA** | `src/data/demo_provider.py` | **YES** | 仅在后台网络中断或用户显式切换 Demo 时启用 |
| **AI Quant Research Report** | LLM + Deterministic Facts | **REAL RESEARCH RESULT** | `src/ai/report_generator.py` | **YES** | 结合 Python 真实指标生成的 Markdown/JSON 报告 |

---

## 3. Anti-Data-Leakage & Statistical Integrity Check

1. **Look-Ahead Bias Protection**: `PITFundamentalProvider` 校验 $\text{cutoff\_date} \ge \text{publication\_date}$，防止未来财报数据提前泄漏；
2. **Train / Test Overlap**: Walk-Forward Runner 强制执行严格时间切分（如 Fold 1: Train 2018-2021, Test 2022），测试集在滚动训练过程中无重叠；
3. **Reproducibility Guarantee**: 任意实验运行均落盘包含 `git_commit`, `data_version_hash`, `universe`, `config` 的 `ExperimentRecord`，保证两次重跑结果 100% 精确一致。
