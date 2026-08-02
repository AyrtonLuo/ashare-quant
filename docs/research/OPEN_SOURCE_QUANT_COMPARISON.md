# 📊 Open-Source Quant Framework Comparison Matrix

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-003`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Quantitative Framework Comparison Matrix

| System / Framework | Data Layer Architecture | Factor & Signal Engine | Backtesting Design | Risk Engine Integration | Experiment Tracking | Key Strengths | Key Weaknesses | Adoption Strategy in AI Quant Pro |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Microsoft Qlib** | Binary Columnar (`$close`, `$open`) | High-performance Expression Engine | Vectorized + Simulator | Basic Position Limits | Built-in MLflow Recorder | SOTA AI/ML workflows, fast matrix computations | Opaque binary format, steep learning curve, US/CN data defaults | **ADOPT CONCEPT**: Expression pipeline, Z-score neutralization, Experiment Recorder |
| **Backtrader** | Line-based DataFeeds (`bt.feeds`) | Indicator-based (`bt.indicators`) | Event-driven (bar-by-bar) | Basic Broker limits | Minimal / File logging | Highly flexible event loop, multi-asset | Slow execution for large multi-factor universes | **ADOPT CONCEPT**: Event-driven backtest rules & slippage/commission models |
| **Zipline / PyFolio** | Data Bundles (Bcolz / HDF5) | Pipeline API (`zipline.pipeline`) | Daily & Minute Event-driven | Basic Risk API | PyFolio Performance Tear Sheets | Rigorous Point-in-Time Pipeline API, benchmark integration | Unmaintained legacy codebase, complex installation | **ADOPT CONCEPT**: Strict Point-in-Time Data Pipeline API |
| **QuantConnect (LEAN)** | Custom Slice & DataFeed Interfaces | Multi-factor & Indicator modules | Multi-asset Event-driven | Institutional Risk Manager | Cloud Backtest Logs | Institutional-grade multi-asset architecture (US, Crypto, FX) | Heavy C# codebase, cloud-centric overhead | **ADOPT CONCEPT**: Canonical Security Master & Corporate Action event contracts |
| **vn.py** | Database Adapters (MongoDB / MySQL) | Strategy CTA Engine | Tick & Bar Event-driven | Gateway Risk Controls | Local SQLite Logs | Chinese A-Share & Futures CTP broker connectivity | Weak quant research & factor analysis tooling | **REJECT AS BACKEND**: Keep for future broker gateway references only |

---

## 2. Synthesis: What We Adopt, Reject, & Build

### What We Adopt:
1. **From Qlib**: Feature expression processing, Z-score cross-sectional neutralization, and structured experiment lineage tracking.
2. **From Zipline**: Point-in-Time publication date enforcement to eliminate look-ahead bias.
3. **From QuantConnect**: Canonical Data Contract abstraction layer separating data providers from Quant Engines.

### What We Reject:
1. **Opaque Binary Formats**: We reject non-standard binary files in favor of DuckDB + Parquet and Pydantic/DataClass schemas.
2. **Framework Lock-In**: We reject wrapping our application in heavy third-party framework bases (e.g. extending `bt.Strategy` or `qlib.Workflow`).

### What We Build Ourselves:
1. **The Data Trust Layer & DataTrustGate**: Independent cross-provider validation, quality scoring, and negative EPS PE/PB handling.
2. **Plain-Language AI Research Copilot Integration**: Seamless bridge between deterministic Quant math and user-friendly explanation interfaces.
