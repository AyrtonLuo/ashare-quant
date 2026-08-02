# 🔒 Research Reproducibility Specification — SHA-256 Manifest & Golden Backtest

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-006A`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. ResearchRunManifest Provenance

`ResearchRunManager` computes cryptographic SHA-256 hashes of dataset payloads and strategy parameters to emit `ResearchRunManifest`. Two backtest runs with identical hashes yield 100% identical outputs (`test_golden_backtest.py`).
