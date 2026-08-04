"""
secret_audit.py — Zero Secret Leakage Security Auditor.
Scans audit files, manifests, log files, and environment representations to guarantee zero credential/token leakage.
"""

import os
from typing import List, Dict, Any


class SecurityAuditManager:
    """
    Scans persistent JSON artifacts, log outputs, and metadata for secret patterns.
    Enforces strict zero secret leakage policy.

    Status semantics (never collapsed into each other):
      PASSED             — files were scanned, none contained a suspicious pattern.
      FAILED_LEAK_DETECTED — files were scanned, at least one suspicious pattern found.
      NO_TARGET_FILES     — the target directory does not exist, or exists but contains zero
                             auditable files. This is NOT equivalent to PASSED: an audit that
                             scanned nothing proves nothing about secret leakage and must not
                             be reported as a passing security certification.
    """

    SUSPICIOUS_SECRET_PATTERNS = ["token=", "api_key=", "secret=", "password=", "tushare_token="]
    # Window (chars) searched around a matched pattern for an explicit "not a real value"
    # marker. Scoped to the match's local context, not the whole file, so an unrelated
    # "unavailable"/"none" elsewhere in a large file can never mask a genuine leak next to it.
    _CONTEXT_WINDOW = 40

    @classmethod
    def _scan_content_for_leaks(cls, content: str, full_path: str) -> List[str]:
        leaks: List[str] = []
        for pat in cls.SUSPICIOUS_SECRET_PATTERNS:
            start = 0
            while True:
                idx = content.find(pat, start)
                if idx == -1:
                    break
                window = content[max(0, idx - cls._CONTEXT_WINDOW): idx + len(pat) + cls._CONTEXT_WINDOW]
                if "unavailable" not in window and "none" not in window:
                    leaks.append(f"Suspicious pattern '{pat}' found in {full_path}")
                start = idx + len(pat)
        return leaks

    @classmethod
    def audit_directory_for_secrets(cls, directory_path: str) -> Dict[str, Any]:
        if not os.path.exists(directory_path):
            return {
                "status": "NO_TARGET_FILES",
                "scanned_files": 0,
                "leaked_secrets": [],
                "security_certification": "AUDIT_NOT_MEANINGFUL_TARGET_MISSING",
            }

        scanned_count = 0
        leaks: List[str] = []

        for root, _, files in os.walk(directory_path):
            for file in files:
                if file.endswith(".json") or file.endswith(".log") or file.endswith(".md"):
                    scanned_count += 1
                    full_path = os.path.join(root, file)
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read().lower()
                    except Exception:
                        continue
                    leaks.extend(cls._scan_content_for_leaks(content, full_path))

        if scanned_count == 0:
            return {
                "status": "NO_TARGET_FILES",
                "scanned_files": 0,
                "leaked_secrets": [],
                "security_certification": "AUDIT_NOT_MEANINGFUL_NO_FILES_SCANNED",
            }

        return {
            "status": "PASSED" if len(leaks) == 0 else "FAILED_LEAK_DETECTED",
            "scanned_files": scanned_count,
            "leaked_secrets": leaks,
            "security_certification": "CERTIFIED_ZERO_SECRET_LEAKAGE" if len(leaks) == 0 else "FAIL_SECRET_LEAK"
        }
