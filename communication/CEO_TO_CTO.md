# CEO → CTO Communication Channel

## Current Directive

**Date**: 2026-08-01

**Priority**: HIGH

**Objective**: 建立 CEO ↔ CTO 协作操作系统基础设施与 Shared Memory 文件协议。

**Context**: 项目已完成 Phase 16 Step 4.6 (API Alignment)、Step 4.7 (Numerical Truth) 与 Step 4.8 (External Truth Audit)。现暂停 Step 5 开发，先搭建规范的 CEO ↔ CTO 协作架构。

**Requirements**:
1. 检查项目环境，不得覆盖已有配置，不得删除用户数据或 Git 历史；
2. 建立 `PRODUCT.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `DECISIONS.md`, `STATUS.md`；
3. 建立 `communication/CEO_TO_CTO.md`, `communication/CTO_TO_CEO.md`, `communication/REVIEW.md`；
4. 建立 `tasks/TODO.md`, `tasks/IN_PROGRESS.md`, `tasks/DONE.md`；
5. 配置 CTO Agent Rules (`.agents/rules/cto.md`)；
6. 不进行任何具体产品功能开发；
7. 输出完整的 CEO ↔ CTO System Setup Report。

**Constraints**:
- 严禁把 secrets / API keys 写进 Git；
- 绝不伪造测试假行情或降级补 0；
- 遵循确定性 8 步工作循环 (`READ -> UNDERSTAND -> PLAN -> EXECUTE -> VERIFY -> REVIEW -> REPORT -> UPDATE`)。

**Acceptance Criteria**:
- 所有的通信与状态文件规范建齐；
- Pytest 全量测试 100% 保持绿灯；
- 提交 Git 本地 Commit。

**Technical Notes**:
- CEO (ChatGPT) 会通过修改本文件或者向 Founder 发送 Markdown 内容下达 Directive。

**Do Not Do**:
- 不要擅自进入 Phase 16 Step 5 开发 Multi-Agent Swarm 或 UI。

**Expected Deliverable**:
- 全套系统文件与 CEO ↔ CTO System Setup Report。
