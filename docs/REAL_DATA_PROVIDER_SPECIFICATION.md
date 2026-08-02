# 🔌 Real Data Provider Specification — Environment & Credential Infrastructure

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-004`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Credential Security & Environment Isolation

- **Zero Credential Hardcoding**: API tokens (e.g., TuShare Pro tokens) must NEVER be committed to Git or hardcoded in Python files.
- **Environment Template**: `.env.example` defines token variables (`TUSHARE_TOKEN`).
- **Sanitized Fixtures**: Offline integration testing utilizes sanitized JSON payloads in `tests/data/real/sanitized_snapshots.json`.
