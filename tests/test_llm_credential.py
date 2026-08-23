"""
test_llm_credential.py — LLMProviderCredentialPreflight. Never requires a real API key —
uses monkeypatch to control the environment deterministically, per the directive's explicit
"不要为了测试要求真实 API key" and "不要接入真实 API 作为测试依赖".
"""

from src.llm.credential import LLMProviderCredentialPreflight


def test_missing_credential_reports_unavailable(monkeypatch):
    monkeypatch.delenv("FAKE_LLM_API_KEY", raising=False)
    result = LLMProviderCredentialPreflight.inspect_credentials("fake_llm", "FAKE_LLM_API_KEY")
    assert result["credential_status"] == "UNAVAILABLE"
    assert "LLM_PROVIDER_CREDENTIALS_UNAVAILABLE" in result["message"]


def test_invalid_short_credential_reports_invalid(monkeypatch):
    monkeypatch.setenv("FAKE_LLM_API_KEY", "short")
    result = LLMProviderCredentialPreflight.inspect_credentials("fake_llm", "FAKE_LLM_API_KEY")
    assert result["credential_status"] == "INVALID"


def test_present_credential_reports_present_unverified(monkeypatch):
    monkeypatch.setenv("FAKE_LLM_API_KEY", "sk-fake1234567890abcdef")
    result = LLMProviderCredentialPreflight.inspect_credentials("fake_llm", "FAKE_LLM_API_KEY")
    assert result["credential_status"] == "PRESENT_UNVERIFIED"


def test_credential_value_never_appears_in_result(monkeypatch):
    secret_value = "sk-super-secret-value-should-never-leak-1234567890"
    monkeypatch.setenv("FAKE_LLM_API_KEY", secret_value)
    result = LLMProviderCredentialPreflight.inspect_credentials("fake_llm", "FAKE_LLM_API_KEY")
    assert secret_value not in str(result)
    assert secret_value not in result["message"]


def test_provider_id_echoed_back(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY_TEST_ONLY", raising=False)
    result = LLMProviderCredentialPreflight.inspect_credentials("claude_primary", "ANTHROPIC_API_KEY_TEST_ONLY")
    assert result["provider_id"] == "claude_primary"
