"""
credential.py — LLM Provider Credential Pre-Flight.

Mirrors src/data/providers/preflight.py::ProviderCredentialPreflight exactly: never prints,
logs, or exposes the actual key value; reports a clear, explicit status instead. Generic over
provider_id/env_var_name (rather than one hardcoded method per vendor) because the directive's
own goal is `OpenAI ↔ Claude ↔ Gemini` swappability — three near-identical hardcoded methods
would duplicate exactly the logic this function already generalizes correctly.
"""

import os
from typing import Any, Dict


class LLMProviderCredentialPreflight:
    """Enforces zero secret leakage in logs, reports, or exceptions — same guarantee
    ProviderCredentialPreflight already makes for TuShare, extended to LLM providers."""

    @staticmethod
    def inspect_credentials(provider_id: str, env_var_name: str) -> Dict[str, Any]:
        key = os.environ.get(env_var_name)
        if not key:
            return {
                "provider_id": provider_id,
                "credential_status": "UNAVAILABLE",
                "message": (
                    f"LLM_PROVIDER_CREDENTIALS_UNAVAILABLE: {env_var_name} environment "
                    "variable not set."
                ),
            }
        if len(key.strip()) < 10:
            return {
                "provider_id": provider_id,
                "credential_status": "INVALID",
                "message": f"{env_var_name} format invalid.",
            }
        # Structural presence/shape check only — this codebase does not make a live network
        # call to a real LLM vendor anywhere (the directive explicitly prohibits it as a test
        # dependency, and no real provider implementation exists in this phase — see
        # provider_base.py's module docstring). A real implementation would add a connectivity
        # probe here, matching ProviderCredentialPreflight.inspect_tushare_credentials()'s
        # pattern, without ever logging the key itself.
        return {
            "provider_id": provider_id,
            "credential_status": "PRESENT_UNVERIFIED",
            "message": (
                f"{env_var_name} is present and structurally well-formed. No live connectivity "
                "probe was attempted — no real LLM provider implementation exists in this phase."
            ),
        }
