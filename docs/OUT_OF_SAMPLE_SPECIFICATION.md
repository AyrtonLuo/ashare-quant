# 📅 Out-of-Sample Specification — Chronological Train / Val / Test Splits

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-006B`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Time-Series Splitting Protocol

To prevent data leakage, historical time-series trading dates are split chronologically without random shuffling:
- **Train Period**: 60%
- **Validation Period**: 20%
- **Out-of-Sample Test Period**: 20%
