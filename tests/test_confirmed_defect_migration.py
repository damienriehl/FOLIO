from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from ontology_qa.debt import debt_root_id, load_debt, publish_migration_receipt, validate_debt_targets
from ontology_qa.correction_pipeline import correction_response_schema
from run_confirmed_defect_corrections import (
    _require_exact_verdicts, build_debt_records,
)

ROOT = Path(__file__).parents[1]
DEBT = ROOT / "qa/ontology/confirmed-defects.json"


def test_confirmed_debt_matches_exact_current_ontology_values():
    entries = load_debt(DEBT)
    matched = validate_debt_targets(ROOT / "FOLIO.owl", entries)
    assert len(entries) == len(matched) == 12


def test_debt_file_contains_no_model_replacements():
    entries = load_debt(DEBT)
    assert all("replacement" not in entry for entry in entries)
    assert all(entry.get("finding") for entry in entries)


def test_debt_records_bind_audit_finding_and_exact_literal():
    entries = load_debt(DEBT)
    records = build_debt_records(ROOT / "FOLIO.owl", entries)
    assert len(records) == 12
    assert {record["record_id"] for record in records} == {
        debt_root_id(entry) for entry in entries
    }
    assert all(record["confirmed_defect"]["finding"] for record in records)
    assert all(record["context"]["context_hash"] for record in records)


def test_dual_review_gate_requires_exact_high_confidence_verdicts():
    records = [{"record_id": "a" * 64}]
    _require_exact_verdicts(
        records,
        [{"record_id": "a" * 64, "verdict": "defect", "confidence": 0.99}],
        verdict="defect", minimum_confidence=0.9,
    )
    with pytest.raises(ValueError, match="did not converge"):
        _require_exact_verdicts(
            records,
            [{"record_id": "a" * 64, "verdict": "defect", "confidence": 0.5}],
            verdict="defect", minimum_confidence=0.9,
        )


def test_correction_roles_have_provider_visible_closed_constraints():
    schema = {
        "type": "object",
        "properties": {
            "verdict": {"enum": ["pass", "defect"]},
            "proposed_replacement": {"type": ["string", "null"]},
        },
        "allOf": [{"if": {}, "then": {}}],
    }
    proposer = correction_response_schema(schema, role="proposer")
    verifier = correction_response_schema(schema, role="verifier")
    assert proposer["properties"]["verdict"] == {"enum": ["defect"]}
    assert proposer["properties"]["proposed_replacement"]["type"] == "string"
    assert verifier["properties"]["proposed_replacement"] == {"type": "null"}
    assert "allOf" not in proposer


def test_stale_hash_or_missing_target_blocks(tmp_path):
    entries = load_debt(DEBT)
    entries[0] = {**entries[0], "current_hash": "0" * 64}
    with pytest.raises(ValueError, match="stale"):
        validate_debt_targets(ROOT / "FOLIO.owl", entries)


def test_interrupted_or_partial_batch_publishes_no_receipt(tmp_path):
    entries = load_debt(DEBT)
    report = {"artifact_hash": "r" * 64, "payload": {"release_decision": "merge_gate_passed"}}
    destination = tmp_path / "receipt.json"
    with pytest.raises(ValueError, match="incomplete"):
        publish_migration_receipt(
            destination, entries=entries, correction_ledger=[],
            release_report=report, final_ontology_path=ROOT / "FOLIO.owl",
        )
    assert not destination.exists()


def test_failed_release_keeps_all_debt_open(tmp_path):
    entries = load_debt(DEBT)
    report = {"artifact_hash": "r" * 64, "payload": {"release_decision": "blocked"}}
    with pytest.raises(ValueError, match="passing"):
        publish_migration_receipt(
            tmp_path / "receipt.json", entries=entries,
            correction_ledger=[], release_report=report,
            final_ontology_path=ROOT / "FOLIO.owl",
        )
    assert all(entry["state"] == "open" for entry in entries)


def test_complete_verified_batch_emits_one_atomic_receipt(tmp_path):
    entries = load_debt(DEBT)
    ledger = [
        {"root_record_id": debt_root_id(entry), "revision_id": f"{index:064x}"}
        for index, entry in enumerate(entries, 1)
    ]
    report = {"artifact_hash": "a" * 64, "payload": {"release_decision": "merge_gate_passed"}}
    receipt = publish_migration_receipt(
        tmp_path / "receipt.json", entries=entries, correction_ledger=ledger,
        release_report=report, final_ontology_path=ROOT / "FOLIO.owl",
    )
    assert len(receipt["closed_debt_ids"]) == 12
