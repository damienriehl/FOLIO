from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from ontology_qa.debt import debt_root_id, load_debt, publish_migration_receipt, validate_debt_targets

ROOT = Path(__file__).parents[1]
DEBT = ROOT / "qa/ontology/confirmed-defects.json"


def test_confirmed_debt_matches_exact_current_ontology_values():
    entries = load_debt(DEBT)
    matched = validate_debt_targets(ROOT / "FOLIO.owl", entries)
    assert len(entries) == len(matched) == 12


def test_debt_file_contains_no_model_replacements():
    assert all("replacement" not in entry for entry in load_debt(DEBT))


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
