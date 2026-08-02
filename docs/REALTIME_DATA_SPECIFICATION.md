# ⚡ Real-Time Data Specification — Ingestion & Latency Models

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-01-REBUILD-003`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Status**: APPROVED FOR EXECUTION  

---

## 1. Latency Classification Model

The platform strictly tags data streams with latency labels:
1. `REALTIME`: Latency $< 1000\text{ ms}$ (Live Websocket / Order Book Feed).
2. `NEAR_REALTIME`: Latency $1\text{ s} - 15\text{ s}$ (3-second snapshot tick feeds).
3. `DELAYED`: Latency $> 15\text{ mins}$ (Delayed public exchange feeds).
4. `END_OF_DAY`: Daily close summary bars.

**Strict Prohibition**: UI is strictly forbidden from displaying `DELAYED` data labeled as `REALTIME`.
