# 📦 Dual-Repository Separation & Migration Audit Report

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-005`  
**Audit Target**: `/Users/yuhanluo/ashare-quant` & `/Users/yuhanluo/ai-quant-bridge`  

---

## 1. Classification & File Audit Matrix

| Item / Directory | Original Location | Target Location | Category | Reason & Dependencies | Migration Status |
| :--- | :--- | :--- | :---: | :--- | :---: |
| `src/` | `ashare-quant/src` | `ashare-quant/src` | **CAT-A** | Quant Core Logic (Contracts, Factors, Research, Orchestrator) | **STAYS IN QUANT** |
| `tests/` | `ashare-quant/tests` | `ashare-quant/tests` | **CAT-A** | Quant Test Suite (313 Passed 100% Green) | **STAYS IN QUANT** |
| `app.py` | `ashare-quant/app.py` | `ashare-quant/app.py` | **CAT-A** | Streamlit Product Entry Point | **STAYS IN QUANT** |
| `communication/` | `ashare-quant/communication` | `ai-quant-bridge/communication` | **CAT-B** | CEO ↔ CTO Communication Protocol Files | **MIGRATED TO BRIDGE** |
| `tasks/` | `ashare-quant/tasks` | `ai-quant-bridge/tasks` | **CAT-B** | Task Protocol (TODO, IN_PROGRESS, DONE) | **MIGRATED TO BRIDGE** |
| `.agents/rules/cto.md` | `ashare-quant/.agents/rules` | `ai-quant-bridge/.agents/rules` | **CAT-B** | Antigravity CTO 8-Step Execution Rules | **MIGRATED TO BRIDGE** |
| `.agents/mcp_config.json` | `ashare-quant/.agents/` | `ai-quant-bridge/.agents/` | **CAT-B** | Bridge MCP Workspace Configuration | **MIGRATED TO BRIDGE** |
| `PRODUCT.md` | `ashare-quant/PRODUCT.md` | Dual Presence | **CAT-C** | Quant Product Vision vs Bridge Product Vision | **SPLIT & DUAL** |
| `ARCHITECTURE.md` | `ashare-quant/ARCHITECTURE.md` | Dual Presence | **CAT-C** | Quant Pipeline Arch vs Bridge Ecosystem Arch | **SPLIT & DUAL** |
| `ROADMAP.md` | `ashare-quant/ROADMAP.md` | Dual Presence | **CAT-C** | Quant Feature Roadmap vs Bridge Infrastructure Roadmap | **SPLIT & DUAL** |
| `DECISIONS.md` | `ashare-quant/DECISIONS.md` | Dual Presence | **CAT-C** | Engineering Decisions vs Infrastructure Decisions | **SPLIT & DUAL** |
| `STATUS.md` | `ashare-quant/STATUS.md` | Dual Presence | **CAT-C** | Quant Build/Test Status vs Bridge Directive Status | **SPLIT & DUAL** |

---

## 2. Cross-Repository Reference Reconciliation

所有路径关联与 Cross-References 规则如下：
- `ai-quant-bridge` 作为主编排与沟通工作区，包含显式路径引用：`/Users/yuhanluo/ashare-quant` 作为其 Engineering Target；
- `ashare-quant` 保持纯粹量化功能，底层算子与测试 100% 正常运行，不受 `ai-quant-bridge` 隔离影响。

---

## 3. Git Status & Repository Isolation

- **Quant Repository**: `/Users/yuhanluo/ashare-quant` (Git Remote: `git@github.com:AyrtonLuo/ashare-quant.git` 保持不变)
- **Bridge Repository**: `/Users/yuhanluo/ai-quant-bridge` (独立本地 Git 仓库，已初始化 `git init`)
