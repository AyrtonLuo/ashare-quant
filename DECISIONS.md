# Decision Log

## Decision 2026-08-01-01: CEO ↔ CTO Collaboration Operating System Infrastructure

### Decision
建立由 Founder 指导、ChatGPT 担任 CEO / Product Architect、Antigravity 担任 CTO / Engineering Agent 的结构化协作文件协议体系。

### Context
随着项目规模扩大与架构深化，Agent 在跨会话重置后容易遗忘历史架构决策与产品约束。需要一个持久化落盘的 Shared Memory 层，解耦战略决策与工程执行。

### Alternatives Considered
1. **单一聊天窗口口头传递**: 容易随着 Context 截断丢失历史上下文；
2. **纯靠代码注释**: 无法有效管理 Product Requirement、Roadmap 与 Code Review 反馈。

### Reason
使用落盘 Markdown 文件作为统一的 Single Source of Truth，具备 100% 可追溯性与确定性。

### Consequences
所有的技术变更与任务分配均遵循 `CEO_TO_CTO.md` -> `CTO_TO_CEO.md` -> `REVIEW.md` 闭环流转。

### Approved By
Founder & CEO


## Decision 2026-08-01-02: Strict Zero-Fallback & Zero Hardcoded Production Values

### Decision
在 Research Mode 下强强制禁止任何 Demo / Mock / 硬编码假数值降级；API 异常时严禁使用 `fillna(0)` 或 `return 0` 静默覆盖。

### Context
量化研究最忌讳伪造数据，`0` 是一个有物理含义的数值（例如零收益），而不能代表数据缺失。

### Alternatives Considered
在网络超时时自动回退到静态历史快照。

### Reason
静态快照在实盘或实时分析时会产生严重的假行清错觉，损害交易系统根基。

### Consequences
API 超时或缺失时必须严格抛出 `SOURCE_ERROR` / `DATA_UNAVAILABLE`，保证量化因子的纯净度。

### Approved By
Founder & CEO
