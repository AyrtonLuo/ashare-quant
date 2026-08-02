# 🔬 Open-Source Quantitative Systems Architecture Research — Microsoft Qlib & Industry Benchmarks

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-003`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Executive Research Purpose

The goal of this research is to study the architectural paradigms, module boundaries, data processing pipelines, and experiment tracking mechanisms of mature open-source quantitative investment frameworks—specifically **Microsoft Qlib**—and adapt their best architectural patterns to our **AI Quantitative Investment Platform**.

**Rule**: Zero code copy-pasting. We extract design principles, module interfaces, and dataset organization, and build our clean, deterministic system.

---

## 2. Microsoft Qlib Architectural Analysis

Microsoft Qlib is an AI-oriented quantitative investment platform. Its architecture is structured around four primary pillars:

```text
┌────────────────────────────────────────────────────────────────────────┐
| 1. DATA LAYER (Qlib Data Format, Feature Processing, Point-in-Time)    |
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Datasets & Features
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
| 2. MODEL LAYER (Signal Forecasting, LightGBM, PyTorch, Alpha Models)   |
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Predictions / Z-Scores
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
| 3. STRATEGY & BACKTEST LAYER (Portfolio Generator, Execution Simulator)|
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Orders & Position Traces
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
| 4. EXPERIMENT & RECORDER LAYER (MLflow-like Trackers, Metrics, Reports)|
└────────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Insights from Qlib:

1. **Binary Columnar Data Storage**:
   - Qlib stores historical daily/minute bar features in compact binary files per field (e.g. `$close`, `$open`, `$volume`), providing lightning-fast data scans across universe $N \times \text{Time } T$.
   - **Adaptation for AI Quant Pro**: We adopt DuckDB + Parquet for high-performance columnar analytical queries while maintaining human-readable auditability and strict Data Contracts.

2. **Feature & Processor Pipeline**:
   - Qlib separates feature expression (e.g., `Ref($close, 1) / $close - 1`) from data processing (e.g., `CSWinsorize`, `CSZscore`).
   - **Adaptation for AI Quant Pro**: Our `FactorEngine` adopts standardized Z-Score normalization and neutralization pipelines, while guaranteeing point-in-time publication date enforcement.

3. **Recorder & Experiment Reproducibility**:
   - Qlib uses a unified `Recorder` interface to record factor definitions, model hyperparameters, predictions, backtest metrics, and order traces.
   - **Adaptation for AI Quant Pro**: Every factor calculation, backtest run, and AI copilot recommendation emits a structured `DataLineageContract` for 100% auditability and reproducibility.

4. **Strategy vs Execution Simulator Separation**:
   - Qlib cleanly separates signal generation (`TopkDropoutStrategy`) from execution simulation (`Simulator`).
   - **Adaptation for AI Quant Pro**: We strictly enforce an independent `RiskEngine` between Signal Generation and Execution Simulation.
