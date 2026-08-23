"""
test_research_analyst_report_identity.py — AI Quant Research Analyst Step 5: Research Report
Identity + Persistence (AI_QUANT_RESEARCH_ANALYST_ARCHITECTURE_PROPOSAL.md §8 / §11 step 5).

Covers the identity contract, provider provenance capture, the immutable store, and — most
importantly — the honest reproducibility scope: the Evidence Bundle is deterministically
verifiable; the AI's prose is not claimed to be bit-reproducible, and these tests assert that
distinction structurally rather than trusting a docstring.
"""

import dataclasses
import json
import os
from datetime import datetime

import pytest

from src.data.contracts.market_data import MarketDataContract
from src.llm.fake_provider import FakeLLMProvider, AlternateFakeLLMProvider
from src.llm.research_analyst import generate_ai_research_output
from src.llm.structured_output import StructuredResearchOutput
from src.quant.evidence.evidence_item import (
    assemble_market_evidence,
    compute_evidence_bundle_hash,
)
from src.quant.reproducibility.canonical import compute_canonical_sha256
from src.quant.research_report.report_identity import (
    NOT_REPORTED_BY_PROVIDER,
    REPORT_IDENTITY_SCHEMA_VERSION,
    REPRODUCIBILITY_SCOPE_EVIDENCE_ONLY,
    ResearchAnalystReportIdentity,
    build_research_analyst_report_identity,
    make_report_id,
    serialize_evidence_bundle_payload,
    verify_report_evidence_integrity,
)
from src.quant.research_report.report_store import ResearchAnalystReportStore

SYMBOL = "600519.SH"
AS_OF = "2026-08-01"


# --- helpers ---------------------------------------------------------------------------------

def _market_evidence(close_price=100.5):
    m = MarketDataContract(
        symbol=SYMBOL, timestamp=datetime(2026, 8, 1), trading_date="2026-08-01",
        open_price=100.0, high_price=101.0, low_price=99.0, close_price=close_price,
        volume=1000.0, amount=100500.0, adj_factor=1.0, unadjusted_close=close_price,
        trading_status="NORMAL", quality_status="VALID", data_origin="GOLDEN_DATASET",
    )
    return assemble_market_evidence(SYMBOL, [m])


def _canned_output(evidence_ids, summary="Price closed at 100.5."):
    return {
        "summary": summary, "technical_analysis": "t", "fundamental_analysis": "f",
        "quant_analysis": "q", "news_analysis": "n", "bull_case": "b", "bear_case": "be",
        "risk_analysis": "r", "conclusion": "c", "evidence_ids": evidence_ids,
    }


def _generate(evidence, provider=None, summary="Price closed at 100.5.", prompt_version="1.0"):
    provider = provider or FakeLLMProvider(
        canned_output=_canned_output([evidence[0].evidence_id], summary=summary)
    )
    return generate_ai_research_output(
        evidence, provider, model="fake-model-1", prompt_version=prompt_version
    )


def _identity_and_payload(evidence, result, **kwargs):
    identity = build_research_analyst_report_identity(
        result, symbol=SYMBOL, as_of=AS_OF, **kwargs
    )
    return identity, serialize_evidence_bundle_payload(evidence)


# --- Identity: the §8 field set ---------------------------------------------------------------

def test_identity_carries_every_proposal_section_8_field():
    evidence = _market_evidence()
    identity, _ = _identity_and_payload(evidence, _generate(evidence))

    field_names = {f.name for f in dataclasses.fields(ResearchAnalystReportIdentity)}
    for required in ("report_id", "symbol", "as_of", "research_run_id", "evidence_bundle_hash",
                     "data_snapshot_id", "model_version", "prompt_version", "code_version",
                     "code_state", "generated_at"):
        assert required in field_names

    assert identity.symbol == SYMBOL
    assert identity.as_of == AS_OF
    assert identity.report_id.startswith(f"report_{SYMBOL}_{AS_OF}_")
    assert identity.schema_version == REPORT_IDENTITY_SCHEMA_VERSION
    assert identity.code_state in ("CLEAN", "DIRTY", "UNAVAILABLE")
    assert identity.generated_at and identity.generated_at != identity.as_of


def test_identity_is_frozen_and_immutable():
    evidence = _market_evidence()
    identity, _ = _identity_and_payload(evidence, _generate(evidence))
    with pytest.raises(dataclasses.FrozenInstanceError):
        identity.symbol = "000001.SZ"


def test_report_id_is_unique_per_report():
    assert make_report_id(SYMBOL, AS_OF) != make_report_id(SYMBOL, AS_OF)


# --- Identity: evidence bundle hash ------------------------------------------------------------

def test_identity_evidence_bundle_hash_matches_bundle():
    evidence = _market_evidence()
    identity, _ = _identity_and_payload(evidence, _generate(evidence))
    assert identity.evidence_bundle_hash == compute_evidence_bundle_hash(evidence)


def test_persisted_payload_hash_matches_compute_evidence_bundle_hash():
    """The persisted projection and the hashed projection must be the same thing — if they ever
    diverge, every stored report silently fails its own integrity check."""
    evidence = _market_evidence()
    payload = serialize_evidence_bundle_payload(evidence)
    assert compute_canonical_sha256(payload) == compute_evidence_bundle_hash(evidence)


def test_evidence_bundle_hash_changes_with_evidence_content():
    a = _market_evidence(close_price=100.5)
    b = _market_evidence(close_price=101.5)
    id_a, _ = _identity_and_payload(a, _generate(a))
    result_b = generate_ai_research_output(
        b, FakeLLMProvider(canned_output=_canned_output([b[0].evidence_id], summary="Price closed at 101.5.")),
        model="fake-model-1",
    )
    id_b, _ = _identity_and_payload(b, result_b)
    assert id_a.evidence_bundle_hash != id_b.evidence_bundle_hash


# --- Identity: provider provenance / model_version / prompt_version -----------------------------

def test_identity_captures_provider_provenance():
    evidence = _market_evidence()
    result = _generate(evidence)
    identity = build_research_analyst_report_identity(
        result, symbol=SYMBOL, as_of=AS_OF,
        provider_version="fake-adapter-9.9", data_origin="SYNTHETIC_DATA",
    )
    assert identity.provider_id == "fake_llm_primary"
    assert identity.model == "fake-model-1"
    assert identity.model_version == "fake-v1"
    assert identity.provider_version == "fake-adapter-9.9"
    assert identity.data_origin == "SYNTHETIC_DATA"
    assert identity.llm_request_id == result.identity.request_id


def test_identity_records_prompt_version_verbatim():
    evidence = _market_evidence()
    result = _generate(evidence, prompt_version="analyst-logic-2.3")
    identity, _ = _identity_and_payload(evidence, result)
    assert identity.prompt_version == "analyst-logic-2.3"


def test_absent_model_version_is_recorded_not_fabricated():
    """AlternateFakeLLMProvider reports model_version=None. The identity must say so explicitly
    rather than inventing a plausible version string."""
    evidence = _market_evidence()
    provider = AlternateFakeLLMProvider(
        canned_output=_canned_output([evidence[0].evidence_id])
    )
    result = generate_ai_research_output(evidence, provider, model="alt-model")
    identity, _ = _identity_and_payload(evidence, result)
    assert result.identity.model_version is None
    assert identity.model_version == NOT_REPORTED_BY_PROVIDER
    assert identity.provider_id == provider.provider_id


def test_unsupplied_provider_version_and_origin_are_recorded_not_fabricated():
    evidence = _market_evidence()
    identity, _ = _identity_and_payload(evidence, _generate(evidence))
    assert identity.provider_version == NOT_REPORTED_BY_PROVIDER
    assert identity.data_origin == NOT_REPORTED_BY_PROVIDER


# --- Identity: Mode A / Mode B linkage ---------------------------------------------------------

def test_mode_a_links_research_run_and_snapshot():
    evidence = _market_evidence()
    identity, _ = _identity_and_payload(
        evidence, _generate(evidence),
        research_run_id="run_abc123", data_snapshot_id="snap_xyz",
    )
    assert identity.research_run_id == "run_abc123"
    assert identity.data_snapshot_id == "snap_xyz"


def test_mode_b_leaves_run_and_snapshot_none_never_fabricated():
    evidence = _market_evidence()
    identity, _ = _identity_and_payload(evidence, _generate(evidence))
    assert identity.research_run_id is None
    assert identity.data_snapshot_id is None


# --- Identity: fail-closed validation -----------------------------------------------------------

def _valid_identity_kwargs(**overrides):
    kwargs = dict(
        report_id="report_x", symbol=SYMBOL, as_of=AS_OF, research_run_id=None,
        evidence_bundle_hash="a" * 64, data_snapshot_id=None, model_version="m",
        prompt_version="1.0", code_version="abc", code_state="CLEAN",
        generated_at="2026-08-01T10:00:00",
    )
    kwargs.update(overrides)
    return kwargs


@pytest.mark.parametrize("field_name", [
    "report_id", "symbol", "as_of", "evidence_bundle_hash", "model_version",
    "prompt_version", "code_version", "code_state", "generated_at",
])
def test_identity_rejects_empty_required_field(field_name):
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        ResearchAnalystReportIdentity(**_valid_identity_kwargs(**{field_name: ""}))


@pytest.mark.parametrize("field_name", ["research_run_id", "data_snapshot_id"])
def test_identity_rejects_empty_string_optional_link(field_name):
    """None means "genuinely absent". "" would be a fabricated link to a nonexistent artifact."""
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        ResearchAnalystReportIdentity(**_valid_identity_kwargs(**{field_name: ""}))
    # None remains valid.
    ResearchAnalystReportIdentity(**_valid_identity_kwargs(**{field_name: None}))


# --- The honest reproducibility scope ------------------------------------------------------------

def test_identity_declares_evidence_only_reproducibility_scope():
    evidence = _market_evidence()
    identity, _ = _identity_and_payload(evidence, _generate(evidence))
    assert identity.reproducibility_scope == REPRODUCIBILITY_SCOPE_EVIDENCE_ONLY
    assert "EVIDENCE_BUNDLE_DETERMINISTICALLY_VERIFIABLE" in identity.reproducibility_scope
    assert "AI_PROSE_NOT_BIT_REPRODUCIBLE" in identity.reproducibility_scope


def test_reproducibility_scope_cannot_be_overridden_to_a_stronger_claim():
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        ResearchAnalystReportIdentity(
            **_valid_identity_kwargs(reproducibility_scope="FULLY_REPRODUCIBLE")
        )


def test_identity_carries_no_hash_over_ai_prose():
    """Structural proof of the claim: unlike ResearchRunIdentity, this identity has no
    result_hash — nothing here asserts the narrative is byte-stable."""
    field_names = {f.name for f in dataclasses.fields(ResearchAnalystReportIdentity)}
    assert "result_hash" not in field_names
    assert not any("prose" in n or "narrative" in n for n in field_names)


def test_same_evidence_different_prose_both_persist_and_both_verify(tmp_path):
    """Two reports over the SAME evidence with DIFFERENT wording: both share one
    evidence_bundle_hash and both pass evidence verification — the deterministic guarantee is
    about the evidence, and is entirely independent of what the model chose to write."""
    store = ResearchAnalystReportStore(base_dir=str(tmp_path / "reports"))
    evidence = _market_evidence()

    ids = []
    for summary in ("Price closed at 100.5.", "The close was 100.5 for the session."):
        result = _generate(evidence, summary=summary)
        identity, payload = _identity_and_payload(evidence, result)
        ids.append(store.create_report(identity, result.output, payload))

    a, b = (store.get_report(i) for i in ids)
    assert a["identity"].report_id != b["identity"].report_id
    assert a["output"].summary != b["output"].summary
    assert a["identity"].evidence_bundle_hash == b["identity"].evidence_bundle_hash
    assert verify_report_evidence_integrity(a["identity"], a["evidence_payload"])
    assert verify_report_evidence_integrity(b["identity"], b["evidence_payload"])


# --- Store: round trip and persistence -----------------------------------------------------------

def test_create_and_get_report_round_trip_in_memory(tmp_path):
    store = ResearchAnalystReportStore(base_dir=str(tmp_path / "reports"))
    evidence = _market_evidence()
    result = _generate(evidence)
    identity, payload = _identity_and_payload(evidence, result)

    report_id = store.create_report(identity, result.output, payload)
    loaded = store.get_report(report_id)

    assert loaded["identity"] == identity
    assert loaded["output"] == result.output
    assert loaded["evidence_payload"] == payload


def test_report_survives_a_fresh_store_instance_from_disk(tmp_path):
    base = str(tmp_path / "reports")
    evidence = _market_evidence()
    result = _generate(evidence)
    identity, payload = _identity_and_payload(evidence, result)
    report_id = ResearchAnalystReportStore(base_dir=base).create_report(
        identity, result.output, payload
    )

    reloaded = ResearchAnalystReportStore(base_dir=base).get_report(report_id)
    assert isinstance(reloaded["identity"], ResearchAnalystReportIdentity)
    assert isinstance(reloaded["output"], StructuredResearchOutput)
    assert reloaded["identity"] == identity
    assert reloaded["output"] == result.output
    assert reloaded["evidence_payload"] == payload
    assert reloaded["identity"].reproducibility_scope == REPRODUCIBILITY_SCOPE_EVIDENCE_ONLY


def test_persisted_files_are_the_three_expected_artifacts(tmp_path):
    base = str(tmp_path / "reports")
    evidence = _market_evidence()
    result = _generate(evidence)
    identity, payload = _identity_and_payload(evidence, result)
    report_id = ResearchAnalystReportStore(base_dir=base).create_report(
        identity, result.output, payload
    )
    assert sorted(os.listdir(os.path.join(base, report_id))) == [
        "evidence_bundle.json", "report_metadata.json", "structured_output.json",
    ]


def test_get_report_returns_none_for_unknown_id(tmp_path):
    store = ResearchAnalystReportStore(base_dir=str(tmp_path / "reports"))
    assert store.get_report("report_does_not_exist") is None
    assert store.get_identity("report_does_not_exist") is None
    assert store.get_evidence_payload("report_does_not_exist") is None


def test_list_reports_and_accessors(tmp_path):
    store = ResearchAnalystReportStore(base_dir=str(tmp_path / "reports"))
    evidence = _market_evidence()
    result = _generate(evidence)
    identity, payload = _identity_and_payload(evidence, result)
    report_id = store.create_report(identity, result.output, payload)

    assert store.list_reports() == [report_id]
    assert store.get_identity(report_id) == identity
    assert store.get_evidence_payload(report_id) == payload


# --- Store: immutability and fail-closed writes ---------------------------------------------------

def test_overwriting_an_existing_report_fails_closed(tmp_path):
    store = ResearchAnalystReportStore(base_dir=str(tmp_path / "reports"))
    evidence = _market_evidence()
    result = _generate(evidence)
    identity, payload = _identity_and_payload(evidence, result)
    store.create_report(identity, result.output, payload)

    with pytest.raises(ValueError, match="IMMUTABLE"):
        store.create_report(identity, result.output, payload)


def test_overwriting_fails_closed_even_for_a_fresh_store_instance(tmp_path):
    base = str(tmp_path / "reports")
    evidence = _market_evidence()
    result = _generate(evidence)
    identity, payload = _identity_and_payload(evidence, result)
    ResearchAnalystReportStore(base_dir=base).create_report(identity, result.output, payload)

    with pytest.raises(ValueError, match="IMMUTABLE"):
        ResearchAnalystReportStore(base_dir=base).create_report(identity, result.output, payload)


def test_empty_evidence_bundle_fails_closed(tmp_path):
    store = ResearchAnalystReportStore(base_dir=str(tmp_path / "reports"))
    evidence = _market_evidence()
    result = _generate(evidence)
    identity, _ = _identity_and_payload(evidence, result)
    with pytest.raises(ValueError, match="FAIL CLOSED"):
        store.create_report(identity, result.output, [])


def test_mismatched_evidence_bundle_hash_fails_closed(tmp_path):
    store = ResearchAnalystReportStore(base_dir=str(tmp_path / "reports"))
    evidence = _market_evidence()
    result = _generate(evidence)
    identity, payload = _identity_and_payload(evidence, result)

    tampered = [dict(payload[0], content="something else entirely")]
    with pytest.raises(ValueError, match="does not match the Evidence"):
        store.create_report(identity, result.output, tampered)
    assert store.list_reports() == []


def test_report_citing_absent_evidence_fails_closed(tmp_path):
    store = ResearchAnalystReportStore(base_dir=str(tmp_path / "reports"))
    evidence = _market_evidence()
    result = _generate(evidence)
    identity, payload = _identity_and_payload(evidence, result)

    forged = StructuredResearchOutput(
        **dict(dataclasses.asdict(result.output), evidence_ids=["MARKET-deadbeef0000"])
    )
    with pytest.raises(ValueError, match="absent from the Evidence Bundle"):
        store.create_report(identity, forged, payload)
    assert store.list_reports() == []


def test_failed_write_leaves_no_partial_report_directory(tmp_path, monkeypatch):
    """The atomic temp-then-rename path: if serialization blows up partway through writing the
    three files, nothing must survive — no report directory under the final id, and no orphaned
    temp directory. Injected at the third write (evidence_bundle.json) so the failure happens
    after two files are already on disk, which is precisely the case a non-atomic write would
    leave visibly broken."""
    import src.quant.research_report.report_store as report_store_module

    base = str(tmp_path / "reports")
    store = ResearchAnalystReportStore(base_dir=base)
    evidence = _market_evidence()
    result = _generate(evidence)
    identity, payload = _identity_and_payload(evidence, result)

    real_to_canonical_json = report_store_module.to_canonical_json
    calls = {"n": 0}

    def exploding_to_canonical_json(data):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("simulated serialization failure mid-write")
        return real_to_canonical_json(data)

    monkeypatch.setattr(report_store_module, "to_canonical_json", exploding_to_canonical_json)

    with pytest.raises(RuntimeError, match="simulated serialization failure"):
        store.create_report(identity, result.output, payload)

    assert calls["n"] == 3, "the failure must have been injected mid-write, not before it"
    assert os.listdir(base) == []
    assert store.get_report(identity.report_id) is None

    # And the id is still free: the aborted attempt did not claim it.
    monkeypatch.setattr(report_store_module, "to_canonical_json", real_to_canonical_json)
    assert store.create_report(identity, result.output, payload) == identity.report_id


# --- Store: corruption handling --------------------------------------------------------------------

def test_corrupted_persisted_file_fails_closed_on_read(tmp_path):
    base = str(tmp_path / "reports")
    evidence = _market_evidence()
    result = _generate(evidence)
    identity, payload = _identity_and_payload(evidence, result)
    report_id = ResearchAnalystReportStore(base_dir=base).create_report(
        identity, result.output, payload
    )

    with open(os.path.join(base, report_id, "report_metadata.json"), "w") as f:
        f.write("{not valid json")

    with pytest.raises(RuntimeError, match="FAIL CLOSED: corrupted persisted file"):
        ResearchAnalystReportStore(base_dir=base).get_report(report_id)


# --- Evidence integrity verification -------------------------------------------------------------

def test_verify_report_evidence_integrity_true_for_untampered_report(tmp_path):
    base = str(tmp_path / "reports")
    evidence = _market_evidence()
    result = _generate(evidence)
    identity, payload = _identity_and_payload(evidence, result)
    report_id = ResearchAnalystReportStore(base_dir=base).create_report(
        identity, result.output, payload
    )

    loaded = ResearchAnalystReportStore(base_dir=base).get_report(report_id)
    assert verify_report_evidence_integrity(loaded["identity"], loaded["evidence_payload"]) is True


def test_verify_report_evidence_integrity_detects_post_hoc_tampering(tmp_path):
    base = str(tmp_path / "reports")
    evidence = _market_evidence()
    result = _generate(evidence)
    identity, payload = _identity_and_payload(evidence, result)
    report_id = ResearchAnalystReportStore(base_dir=base).create_report(
        identity, result.output, payload
    )

    bundle_path = os.path.join(base, report_id, "evidence_bundle.json")
    with open(bundle_path) as f:
        stored = json.load(f)
    stored[0]["content"] = "retroactively altered evidence"
    with open(bundle_path, "w") as f:
        json.dump(stored, f)

    loaded = ResearchAnalystReportStore(base_dir=base).get_report(report_id)
    assert verify_report_evidence_integrity(loaded["identity"], loaded["evidence_payload"]) is False


# --- End-to-end ------------------------------------------------------------------------------------

def test_end_to_end_evidence_to_persisted_verified_report(tmp_path):
    store = ResearchAnalystReportStore(base_dir=str(tmp_path / "reports"))
    evidence = _market_evidence()
    provider = FakeLLMProvider(canned_output=_canned_output([evidence[0].evidence_id]))

    result = generate_ai_research_output(
        evidence, provider, model="fake-model-1", prompt_version="1.0"
    )
    identity = build_research_analyst_report_identity(
        result, symbol=SYMBOL, as_of=AS_OF, research_run_id="run_e2e",
        data_snapshot_id="snap_e2e", provider_version=provider.provider_version,
        data_origin="SYNTHETIC_DATA",
    )
    report_id = store.create_report(
        identity, result.output, serialize_evidence_bundle_payload(evidence)
    )

    loaded = store.get_report(report_id)
    assert loaded["identity"].evidence_bundle_hash == compute_evidence_bundle_hash(evidence)
    assert loaded["identity"].research_run_id == "run_e2e"
    assert loaded["output"].evidence_ids == [evidence[0].evidence_id]
    assert verify_report_evidence_integrity(loaded["identity"], loaded["evidence_payload"])
