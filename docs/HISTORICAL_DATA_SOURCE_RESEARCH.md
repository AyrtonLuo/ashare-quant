# 📚 Historical Data Source Research & Evaluation Matrix

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-005A`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Historical Data Source Evaluation Matrix

| Evaluated Dimension | TuShare Pro (Primary Historical) | AkShare (Secondary Verification) | Choice / Wind (Institutional) | Open CSV / Kaggle (Public Datasets) |
| :--- | :---: | :---: | :---: | :---: |
| **A-Share Daily OHLCV Coverage** | Complete (20+ Years) | Complete (20+ Years) | Complete (30+ Years) | Partial / Unverified |
| **Delisted Stocks Included** | **YES (Prevents Survivorship)** | Partial | YES | **NO (High Bias)** |
| **Corporate Actions (Dividends/Splits)**| Complete | Complete | Complete | Missing / Inconsistent |
| **Point-in-Time Announcement Dates** | **YES (Disclosure Dates)** | Partial | YES | **NO (High Look-Ahead Risk)** |
| **Historical Reproducibility** | High (Token API) | Medium (Web Scraping) | High | Low (Static Snapshot) |
| **Data License & Licensing** | Commercial Token API | Open Source | Enterprise License | Varies / Unclear |

---

## 2. Source Selection Decision & Failure Modes

- **Primary Historical Source**: **TuShare Pro** (Selected for full delisted A-Share coverage, exact corporate action adjustment factors, and disclosure date fields).
- **Secondary Validation Source**: **AkShare** (Selected for cross-provider price and volume sanity checks).
- **Public CSV Datasets**: **REJECTED** due to severe Survivorship Bias (lacking delisted stocks) and missing disclosure timestamps.
