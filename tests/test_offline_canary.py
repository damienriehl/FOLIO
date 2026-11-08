from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from ontology_qa.offline_canary import (
    MANDATORY, PROFILE, build_report, input_identity, markdown, route_observation,
)

ROOT = Path(__file__).resolve().parents[1]


def complete_receipt(outcome="passed"):
    nodes = []
    for paths in PROFILE.values():
        nodes.extend(f"{path}::test_extra" for path in paths)
    nodes.extend(f"tests/test_workflow_contract.py::{name}" for name in MANDATORY)
    nodes = list(dict.fromkeys(nodes))
    return {"collected": nodes, "outcomes": {node: outcome for node in nodes}}


def make_report(receipt, *, exit_code=0, junit=None, issues=None):
    identity = {"fingerprint": "a" * 64}
    return build_report(
        identity=identity, receipt=receipt,
        junit=junit if junit is not None else receipt["outcomes"],
        process_exit=exit_code, routes={"status": "passed", "roles": []},
        extra_issues=issues,
    )


def test_complete_offline_evidence_passes_without_authorizing_release():
    report = make_report(complete_receipt())
    assert report["offline_status"] == "passed"
    assert report["live_qualification"] == "not_run"
    assert report["live_actions"] == "not_verified"
    assert report["release_authorization"] is False
    assert "release_decision" not in report


@pytest.mark.parametrize("mutation", ["empty", "missing", "duplicate", "skipped", "xfailed"])
def test_untrustworthy_or_incomplete_evidence_is_incomplete(mutation):
    receipt = complete_receipt()
    if mutation == "empty":
        receipt = {"collected": [], "outcomes": {}}
    elif mutation == "missing":
        node = receipt["collected"].pop()
        receipt["outcomes"].pop(node)
    elif mutation == "duplicate":
        receipt["collected"].append(receipt["collected"][0])
    else:
        receipt["outcomes"][receipt["collected"][0]] = mutation
    assert make_report(receipt)["offline_status"] == "incomplete"


def test_missing_evidence_precedes_an_observed_failure():
    receipt = complete_receipt()
    receipt["outcomes"][receipt["collected"][0]] = "failed"
    receipt["collected"].pop()
    report = make_report(receipt, exit_code=1)
    assert report["offline_status"] == "incomplete"
    assert report["observed"]["failed"]


def test_complete_failure_is_failed_and_rejection_test_names_add_no_claims():
    receipt = complete_receipt()
    receipt["outcomes"][receipt["collected"][0]] = "failed"
    report = make_report(receipt, exit_code=1)
    assert report["offline_status"] == "failed"
    assert report["release_authorization"] is False


def test_normalized_outputs_ignore_receipt_order_and_operational_noise():
    first = complete_receipt()
    second = {"collected": list(reversed(first["collected"])),
              "outcomes": dict(reversed(list(first["outcomes"].items()))),
              "duration": 42, "traceback": "/tmp/elsewhere"}
    one, two = make_report(first), make_report(second)
    assert json.dumps(one, sort_keys=True) == json.dumps(two, sort_keys=True)
    assert markdown(one) == markdown(two)


def test_input_identity_changes_with_effective_input(tmp_path):
    (tmp_path / "scripts/ontology_qa").mkdir(parents=True)
    source = tmp_path / "scripts/ontology_qa/example.py"
    source.write_text("one")
    first = input_identity(tmp_path)["fingerprint"]
    source.write_text("two")
    assert input_identity(tmp_path)["fingerprint"] != first


def test_current_route_structure_is_complete_and_independent():
    observation = route_observation(ROOT)
    assert observation["status"] == "passed"
    assert len(observation["roles"]) == 6


def test_existing_destination_is_preserved_without_starting_pytest(tmp_path):
    destination = tmp_path / "existing"
    destination.mkdir()
    marker = destination / "marker"
    marker.write_text("preserve")
    result = subprocess.run(
        [sys.executable, "scripts/run_offline_ontology_canary.py", "--output-dir", str(destination)],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 2
    assert marker.read_text() == "preserve"
    assert not (destination / "raw").exists()


def test_real_offline_canary_executes_fixed_profile(tmp_path):
    destination = tmp_path / "canary"
    result = subprocess.run(
        [sys.executable, "scripts/run_offline_ontology_canary.py", "--output-dir", str(destination)],
        cwd=ROOT, text=True, capture_output=True, timeout=180, check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr, (destination / "raw/pytest.log").read_text())
    report = json.loads((destination / "report.json").read_text())
    assert report["offline_status"] == "passed"
    assert all(group["executed"] for group in report["coverage"])
    assert (destination / "raw/junit.xml").is_file()
