# CLAUDE.md — AI Quant Pro Operating Directive & Context Protocol

## 1. Project Identity & Governance Roles

- **Project Name**: AI Quant Pro / `ashare-quant`
- **Purpose**: Institutional-Grade A-Share Quantitative Research, Point-in-Time (PIT) Factor Engine, Backtest Infrastructure, and Research Workbench.
- **Tech Stack**: Python 3.9+, Pytest, DuckDB / Parquet, FastAPI, Vite / HTML / JS / CSS.
- **Governance Roles**:
  - **ChatGPT**: CEO / Strategic Direction & Phase Directives
  - **Antigravity**: CTO / Lead Architecture & System Implementation
  - **Claude**: Coding, Analysis, & Hardening Agent
- **Absolute Scope Boundary**: Research, Backtesting, Factor Analytics, and PIT Data Integrity ONLY. Strictly PROHIBITED: Live broker integration, Order execution, Paper trading, Automatic buy/sell, Real-money execution.

---

## 2. Source of Truth Hierarchy

When resolving project state, specifications, or implementation details, adhere strictly to the following precedence hierarchy:

```text
Actual Repository Code & Specs > Automated Test Suite > Persistent Context Files (.claude/) > Conversation History
```

> **Critical Principle**: Conversation Context is temporary working memory; Git-tracked Repository Files and `.claude/` Context Files are the sole persistent, authoritative source of truth across sessions and agents.

---

## 3. Development & Safety Rules

Before making any code or configuration edits, the agent MUST:
1. Understand the exact assigned task and scope boundaries.
2. Inspect target codebase files using code search and file viewing tools (never guess paths or logic).
3. Read `.claude/CURRENT_STATE.md`, `.claude/HANDOFF.md`, and relevant `.claude/DECISIONS.md`.
4. Inspect `git status` and test suite execution status.
5. Scope modifications strictly to the assigned task.

### Strict Negative Directives (Forbidden Actions):
- **NO Unrelated Refactoring**: Do not touch code outside the immediate task scope.
- **NO Unauthorized Architecture Mutations**: Do not change underlying contracts or APIs without explicit directive.
- **NO Mass Deletions**: Do not delete existing specs, docstrings, or test files.
- **NO Guessing Logic/Schemas**: Always inspect exact function signatures and data structures.
- **NO Superficial Test Patching**: Never bypass failing tests by swallowing exceptions, deleting assertions, returning dummy zeros (`fillna(0)`), or mocking tests just to pass.
- **NO Secret Exposure**: Never log, print, or commit API keys, `TUSHARE_TOKEN`, or environment secrets.
- **NO Trading / Order Routing**: Never connect to live brokers or implement order routing/execution.

---

## 4. Context Budget Protocol & State Machine

Agents must actively monitor context bloat and transition through the **Context State Machine**:

```text
NORMAL
  │
  │ context pressure detected
  ↓
CONTEXT_PRESSURE
  │
  │ state synchronized
  ↓
HANDOFF_READY
  │
  ↓
NEW SESSION / COMPACTION
  │
  ↓
RECOVERY
  │
  ├── read CLAUDE.md
  ├── read CURRENT_STATE.md
  ├── read HANDOFF.md
  ├── read relevant DECISIONS.md
  └── inspect git status
  │
  ↓
NORMAL
```

### Context Operating States:

1. **NORMAL**: Standard execution mode. Read only task-relevant files. Avoid repo-wide exploration.
2. **CONTEXT_PRESSURE**: Activated upon detecting long context, obsolete messages, heavy tool outputs, or upcoming compaction.
   - Halt file exploration.
   - Synchronize new facts to `.claude/CURRENT_STATE.md`.
   - Synchronize new architectural choices to `.claude/DECISIONS.md`.
   - Synchronize current task and next steps to `.claude/HANDOFF.md`.
3. **HANDOFF_READY**: Activated when context approaches safety limit or session is ending.
   - Finalize synchronization of `.claude/CURRENT_STATE.md`, `.claude/DECISIONS.md`, and `.claude/HANDOFF.md`.
   - Set `Handoff Status: READY` in `.claude/HANDOFF.md`.
   - **STOP** further execution immediately.

---

## 5. Multi-Agent Handoff Responsibility Protocol

The context system serves as the shared state bridge for ChatGPT (CEO), Antigravity (CTO), and Claude (Coder):

- `.claude/CURRENT_STATE.md` answers: *"What is the exact current state of the project?"*
- `.claude/DECISIONS.md` answers: *"Why is the project in this state? (Long-term architectural memory)"*
- `.claude/HANDOFF.md` answers: *"Where should the next agent continue from? (Standardized handoff contract)"*

---

## 6. Anti-Context-Pollution Rules

To prevent context bloat and maintain high agent reliability:

1. **Rule 1**: Do NOT scan the entire repository to understand the project.
2. **Rule 2**: Read `CLAUDE.md`, `.claude/CURRENT_STATE.md`, and `.claude/HANDOFF.md` FIRST before taking action.
3. **Rule 3**: Load only files directly relevant to the current task.
4. **Rule 4**: Do NOT re-read information that is already established in context files.
5. **Rule 5**: Do NOT copy raw terminal output into context files.
6. **Rule 6**: Do NOT copy source code into context files.
7. **Rule 7**: Record conclusions and verified facts, not raw processes or temporary debug steps.
8. **Rule 8**: Reports must be concise and context-efficient: state the outcome first, include only
   material changes, test status, risks/blockers, and the exact next action. Avoid repeating known
   background, narrating routine tool steps, or pasting large logs.
9. **Rule 9**: After a requested change is complete and verified, create a local Git commit by
   default. Never push to a remote unless the Product Owner explicitly approves it.

---

## 7. New Session Recovery Protocol

At the start of every NEW session or post-compaction recovery, the agent MUST:

1. Read `CLAUDE.md`.
2. Read `.claude/CURRENT_STATE.md`.
3. Read `.claude/HANDOFF.md`.
4. Read relevant `.claude/DECISIONS.md` (if task involves architecture).
5. Run `git status` via terminal tool.
6. Identify exact task from `HANDOFF.md`.
7. If `HANDOFF.md` has `Handoff Status: READY`, execute the `Exact Next Action` immediately.
8. Inspect only relevant files to execute the action.
