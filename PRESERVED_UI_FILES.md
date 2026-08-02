# 🎨 Preserved Web / Cloud UI Assets Report

**Document Version**: 1.0.0  
**Directive ID**: `CEO-2026-08-02-001`  
**Target Repository**: `/Users/yuhanluo/ashare-quant`  
**Date**: 2026-08-01  

---

## Preserved Web / Cloud UI Inventory

The following files and configurations are strictly preserved as the only allowed legacy assets for the Streamlit Web / Cloud UI:

| File / Asset Path | Purpose | Why Preserved | Dependency |
| :--- | :--- | :--- | :--- |
| `app.py` | Streamlit Web / Cloud UI Application Entry Point | Primary Web UI interface, custom CSS theme, layout rendering, and pages | Streamlit, Pandas, Plotly |
| `.streamlit/config.toml` | Streamlit Configuration | Dark theme, port configuration, headless server settings | Streamlit |
| `requirements.txt` | Core UI Dependencies | Installs Streamlit, Pandas, Plotly, Numpy required for UI rendering | Python pip |
| `README.md` | Product Overview & Setup Guide | Documentation for project setup and Web UI launch | Markdown |
| `.gitignore` | Version Control Exclusions | Ignores `.env`, cache, and bytecode files | Git |
| `ashare-quant.service` | Systemd Service Configuration | Production background service setup for Web UI | Systemd |
| `deploy_server.sh` | Cloud Deployment Script | Automated deployment script for Streamlit server | Shell |
| `nginx_ashare_quant.conf` | Reverse Proxy Configuration | Nginx configuration for production Cloud UI deployment | Nginx |

---

## UI Backend Rebuild Notice
- `app.py` contains UI layout rendering and page sections.
- The legacy backend implementation in `src/` (old data layer, old contracts, old factor engine, old research agents, old backtester, old trading engines) is completely removed as part of the System Reset.
- Future Quant Backend will be rebuilt cleanly from scratch for the Web UI.
