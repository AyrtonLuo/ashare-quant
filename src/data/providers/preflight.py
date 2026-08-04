"""
preflight.py — Live Provider Credential Pre-Flight Verification & Safety Audit.
Safely detects environment credentials without ever printing, logging, or exposing secrets.
"""

import os
import json
from typing import Dict, Any


class ProviderCredentialPreflight:
    """
    Executes pre-flight credential and reachability audit for live data providers.
    Enforces zero secret leakage in logs, reports, or exceptions.
    """

    @staticmethod
    def inspect_tushare_credentials() -> Dict[str, Any]:
        token = os.environ.get("TUSHARE_TOKEN")
        if not token or token == "DEMO_TOKEN":
            return {
                "provider_id": "tushare_pro_primary",
                "credential_status": "UNAVAILABLE",
                "message": "REAL_DATA_CREDENTIALS_UNAVAILABLE: TUSHARE_TOKEN environment variable not set or set to DEMO_TOKEN."
            }

        # Validate token structure (non-empty string check without logging value)
        if len(token.strip()) < 10:
            return {
                "provider_id": "tushare_pro_primary",
                "credential_status": "INVALID",
                "message": "TUSHARE_TOKEN format invalid."
            }

        try:
            import tushare as ts
            pro = ts.pro_api(token)
            # Connectivity probe with 1 symbol
            df = pro.query("stock_basic", exchange="", list_status="L", fields="ts_code,symbol,name")
            if df is not None and not df.empty:
                return {
                    "provider_id": "tushare_pro_primary",
                    "credential_status": "AVAILABLE",
                    "message": "TUSHARE_PRO live API reached and authenticated."
                }
            else:
                return {
                    "provider_id": "tushare_pro_primary",
                    "credential_status": "API_UNREACHABLE",
                    "message": "TuShare Pro API returned empty probe response."
                }
        except Exception as e:
            return {
                "provider_id": "tushare_pro_primary",
                "credential_status": "API_UNREACHABLE",
                "message": f"TuShare Pro connection probe failed."
            }

    @staticmethod
    def run_preflight_audit(audit_dir: str = "/Users/yuhanluo/ashare-quant/data/research/audit/live_provider_verification") -> Dict[str, Any]:
        os.makedirs(audit_dir, exist_ok=True)
        res = ProviderCredentialPreflight.inspect_tushare_credentials()

        report = {
            "preflight_status": res["credential_status"],
            "provider_id": res["provider_id"],
            "message": res["message"],
            "timestamp": "2026-08-03T19:31:00Z"
        }

        with open(os.path.join(audit_dir, "credential_preflight.json"), "w") as f:
            json.dump(report, f, indent=2)

        return report
