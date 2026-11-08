from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
COMMAND = ROOT / "scripts/validate_ontology_annotations.py"


def ontology(body: str) -> str:
    return f'''<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:skos="http://www.w3.org/2004/02/skos/core#">
<rdf:Description rdf:about="https://example.test/C">{body}</rdf:Description>
</rdf:RDF>'''


def run(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(COMMAND), str(path), *args], cwd=ROOT,
        text=True, capture_output=True, check=False, timeout=20,
    )


def test_validator_cli_reports_success_and_writes_requested_output(tmp_path):
    source = tmp_path / "valid.owl"
    source.write_text(ontology('<skos:definition xml:lang="en">Valid.</skos:definition>'))
    completed = run(source)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["status"] == "complete"

    output = tmp_path / "result.json"
    completed = run(source, "--output", str(output))
    assert completed.returncode == 0
    assert completed.stdout == ""
    assert json.loads(output.read_text())["status"] == "complete"


def test_validator_cli_returns_failed_json_for_defect_and_malformed_xml(tmp_path):
    for name, content in (
        ("defect.owl", ontology("<skos:definition>NULL</skos:definition>")),
        ("malformed.owl", "<rdf:RDF>"),
    ):
        source = tmp_path / name
        source.write_text(content)
        completed = run(source)
        assert completed.returncode == 1
        assert json.loads(completed.stdout)["status"] == "failed"


def test_validator_cli_baseline_allows_legacy_debt_but_blocks_regression(tmp_path):
    baseline = tmp_path / "baseline.owl"
    baseline.write_text(ontology("<skos:definition>NULL</skos:definition>"))
    same = run(baseline, "--baseline", str(baseline))
    assert same.returncode == 0
    assert json.loads(same.stdout)["legacy_failure_count"] == 1

    candidate = tmp_path / "candidate.owl"
    candidate.write_text(ontology(
        "<skos:definition>NULL</skos:definition>"
        "<skos:altLabel>['new']</skos:altLabel>"
    ))
    regression = run(candidate, "--baseline", str(baseline))
    assert regression.returncode == 1
    assert json.loads(regression.stdout)["failures"]
