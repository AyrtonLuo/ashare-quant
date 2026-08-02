# 🔄 Data Normalization Specification — Symbol & Currency Standards

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-003`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Symbol Normalization Matrix

Different providers use divergent ticker representations. The Normalization Layer maps all inputs to `Canonical Symbol Format`:

| Provider | Raw Input Example | Canonical Standard Format |
| :--- | :--- | :--- |
| **AkShare** | `"600519"`, `"sh600519"` | `600519.SH` |
| **TuShare Pro** | `"600519.SH"` | `600519.SH` |
| **Choice / Wind** | `"600519.SH"` | `600519.SH` |
| **BaoStock** | `"sh.600519"` | `600519.SH` |
| **Futu** | `"SH.600519"` | `600519.SH` |

---

## 2. Currency & Unit Normalization
- All A-Share market prices and amounts are normalized to **RMB / CNY**.
- Financial statement line items (e.g. Revenue = 140 Billion RMB) are normalized to floating point RMB amounts (e.g. `140000000000.0`), never mixed with "万元" or "亿元" string units.
