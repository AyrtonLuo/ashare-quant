# 🏗️ System Architecture — AI Quantitative Investment Platform

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-001`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. High-Level Layered Architecture

The platform strictly enforces a 6-layer unidirectional architecture to prevent tight coupling, circular dependencies, and unverified data leakage.

```text
+-----------------------------------------------------------------------+
| 1. PRESENTATION LAYER (Web UI / Streamlit / Next.js)                  |
+-----------------------------------------------------------------------+
                                    │ HTTP / WebSocket / JSON
                                    ▼
+-----------------------------------------------------------------------+
| 2. APPLICATION & API LAYER (FastAPI / REST Controllers)                |
+-----------------------------------------------------------------------+
             │                                              │
             ▼ Calling Tools                                ▼ Directly Calls Domain
+---------------------------+             +-----------------------------+
| 3. AI RESEARCH LAYER      |             | 4. QUANT DOMAIN ENGINE      |
| (LLM Agents & Copilot)    |             | (Factors, Signals, Risk)    |
+---------------------------+             +-----------------------------+
             │                                              │
             └──────────────────────┬───────────────────────┘
                                    ▼ Reads Only Canonical Data
+-----------------------------------------------------------------------+
| 5. DATA TRUST LAYER (Normalization, Validation, Lineage, Verification)|
+-----------------------------------------------------------------------+
                                    │ Standard Provider Adapters
                                    ▼
+-----------------------------------------------------------------------+
| 6. DATA PROVIDERS LAYER (AkShare, TuShare, Choice, Custom Feeds)      |
+-----------------------------------------------------------------------+
```

---

## 2. Layer Definitions & Strict Boundaries

### Layer 1: Presentation Layer (Web UI)
- **Role**: Render user interface, stock dashboards, portfolio visualizers, natural language chat interfaces.
- **Strict Constraint**: **PROHIBITED** from importing data provider SDKs, running raw financial math, or directly calling external finance APIs.

### Layer 2: Application Layer (REST Controllers)
- **Role**: Request validation, session management, orchestrating calls between Presentation, AI Layer, and Quant Engine.
- **Strict Constraint**: Contains no core financial calculation logic; delegates strictly to Domain Layer.

### Layer 3: AI Research Layer (LLM Copilot)
- **Role**: Natural language query understanding, tool selection, translating user intent into Quant Engine calls, and formatting Quant Engine outputs into readable explanations.
- **Strict Constraint**: **PROHIBITED** from generating or guessing financial metrics (PE, PB, Volatility, Returns). Must invoke Quant Engine via Data Contracts.

### Layer 4: Quant Domain Engine
- **Sub-engines**: Factor Engine, Signal Engine, Strategy Engine, Portfolio Engine, Risk Engine, Backtest Engine.
- **Strict Constraint**: Operates deterministically on Canonical Data. Zero dependency on LLM APIs or presentation frameworks.

### Layer 5: Data Trust Layer
- **Role**: Provider abstraction, data normalization, cross-source verification, corporate action adjustments, quality scoring, point-in-time enforcement.
- **Strict Constraint**: Serves as the sole data gateway for the Quant Engine. Unvalidated data is blocked.

### Layer 6: Data Provider Layer
- **Role**: Raw API connection to market data feeds (AkShare, TuShare, etc.).
- **Strict Constraint**: Isolated behind Provider Adapters. Provider changes do NOT affect Quant Engine or Web UI.

---

## 3. Core Sub-Engine Flow Diagram

```text
Data Provider Layer -> Data Trust Layer -> Canonical Data Models
                                                  │
                                                  ▼
                                            Factor Engine
                                                  │
                                                  ▼
                                            Signal Engine
                                                  │
                                                  ▼
                                           Strategy Engine
                                                  │
                                                  ▼
                                           Portfolio Engine
                                                  │
                                                  ▼
                                             Risk Engine  <--- (Circuit Breakers)
                                                  │
                                                  ▼
                                           Execution / Sim
```
