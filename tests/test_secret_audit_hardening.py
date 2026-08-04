"""
test_secret_audit_hardening.py — Phase 7I adversarial tests (Directive 007I, Section 12).

Proves the secret auditor distinguishes: real scan / empty scan / missing directory /
secret found / clean scan, and that a match's local "unavailable"/"none" context cannot
mask an unrelated genuine leak elsewhere in the same file.
"""

from src.data.security.secret_audit import SecurityAuditManager


def test_missing_directory_is_not_meaningfully_passed(tmp_path):
    missing = tmp_path / "does_not_exist"
    res = SecurityAuditManager.audit_directory_for_secrets(str(missing))
    assert res["status"] == "NO_TARGET_FILES"
    assert res["status"] != "PASSED"
    assert res["scanned_files"] == 0


def test_empty_directory_is_not_meaningfully_passed(tmp_path):
    res = SecurityAuditManager.audit_directory_for_secrets(str(tmp_path))
    assert res["status"] == "NO_TARGET_FILES"
    assert res["status"] != "PASSED"
    assert res["scanned_files"] == 0


def test_directory_with_only_non_auditable_extensions_is_not_meaningfully_passed(tmp_path):
    (tmp_path / "data.parquet").write_bytes(b"not scanned by extension")
    res = SecurityAuditManager.audit_directory_for_secrets(str(tmp_path))
    assert res["status"] == "NO_TARGET_FILES"
    assert res["scanned_files"] == 0


def test_clean_scan_with_real_files_passes(tmp_path):
    (tmp_path / "report.json").write_text('{"status": "ok", "value": 42}')
    res = SecurityAuditManager.audit_directory_for_secrets(str(tmp_path))
    assert res["status"] == "PASSED"
    assert res["scanned_files"] == 1
    assert res["security_certification"] == "CERTIFIED_ZERO_SECRET_LEAKAGE"


def test_real_secret_pattern_is_detected():
    with_secret = 'token=sk_live_abcdef1234567890'
    leaks = SecurityAuditManager._scan_content_for_leaks(with_secret.lower(), "fake.json")
    assert len(leaks) == 1


def test_secret_scan_end_to_end_detects_leak(tmp_path):
    (tmp_path / "leaky.log").write_text("some log line\ntoken=sk_live_abcdef1234567890\nmore text")
    res = SecurityAuditManager.audit_directory_for_secrets(str(tmp_path))
    assert res["status"] == "FAILED_LEAK_DETECTED"
    assert res["security_certification"] == "FAIL_SECRET_LEAK"
    assert len(res["leaked_secrets"]) == 1


def test_unavailable_marker_suppresses_only_its_local_match():
    text = "TUSHARE_TOKEN unavailable in this environment"
    leaks = SecurityAuditManager._scan_content_for_leaks(text.lower(), "fake.json")
    assert leaks == []


def test_unavailable_elsewhere_in_file_does_not_mask_a_real_leak_nearby():
    """Regression test for a real bug found during Phase 7I audit: the old implementation
    checked for 'unavailable'/'none' anywhere in the WHOLE file, so a genuine leaked secret
    could be hidden simply by the file also containing the word 'unavailable' somewhere
    unrelated (e.g. in an entirely different field). The check must be scoped to the local
    context around each match."""
    text = (
        "credential_preflight_status: unavailable\n"
        "\n" + ("x" * 500) + "\n"
        "token=sk_live_abcdef1234567890_this_is_a_real_leaked_secret\n"
    )
    leaks = SecurityAuditManager._scan_content_for_leaks(text.lower(), "fake.json")
    assert len(leaks) == 1, "a genuine leak far from the 'unavailable' marker must still be caught"
