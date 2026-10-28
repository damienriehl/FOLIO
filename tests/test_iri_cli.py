from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
COMMAND = ROOT / "scripts/mint_iri.py"
sys.path.insert(0, str(ROOT / "scripts"))
import mint_iri

CANONICAL = "R" + "z" * 21


def invoke(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(COMMAND), *args], cwd=ROOT, text=True,
        capture_output=True, check=False, timeout=20,
    )


def test_check_accepts_unused_and_rejects_used_full_or_local_name(tmp_path):
    empty = tmp_path / "empty.owl"
    empty.write_text("<rdf:RDF/>")
    assert invoke("--check", CANONICAL, "--ontology", str(empty)).returncode == 0

    occupied = tmp_path / "occupied.owl"
    occupied.write_text(f'<rdf:Description rdf:about="{mint_iri.FOLIO_NAMESPACE}{CANONICAL}"/>')
    for spelling in (CANONICAL, mint_iri.FOLIO_NAMESPACE + CANONICAL):
        completed = invoke("--check", spelling, "--ontology", str(occupied))
        assert completed.returncode == 1
        assert "already published" in completed.stdout
    assert invoke("--check", "typed-by-hand", "--ontology", str(empty)).returncode == 1


def test_audit_accepts_known_outlier_and_names_new_drift(tmp_path):
    known = tmp_path / "known.owl"
    known.write_text(f'<owl:Class rdf:about="{mint_iri.FOLIO_NAMESPACE}#GovB-US-FD-DHS-HSARPA">')
    assert invoke("--audit", "--ontology", str(known)).returncode == 0
    drift = tmp_path / "drift.owl"
    drift.write_text(f'<owl:Class rdf:about="{mint_iri.FOLIO_NAMESPACE}new-drift">')
    completed = invoke("--audit", "--ontology", str(drift))
    assert completed.returncode == 1
    assert "new-drift" in completed.stdout


def test_mint_delegates_and_adds_each_result_to_collision_set(tmp_path, monkeypatch, capsys):
    source = tmp_path / "source.owl"
    source.write_text("<rdf:RDF/>")
    calls = []
    names = ["R" + "a" * 21, "R" + "b" * 21]

    def generate(used):
        calls.append(set(used))
        return mint_iri.FOLIO_NAMESPACE + names[len(calls) - 1]

    monkeypatch.setattr(mint_iri, "generate_iri", generate)
    args = argparse.Namespace(ontology=[str(source)], count=2)
    assert mint_iri.run_mint(args, ROOT) == 0
    assert names[0] in calls[1]
    assert mint_iri.FOLIO_NAMESPACE + names[0] in calls[1]
    output = capsys.readouterr().out
    assert all(name in output for name in names)


@pytest.mark.parametrize("mode", [(), ("--audit",)])
def test_mint_and_audit_without_ontologies_return_usage_error(tmp_path, mode):
    missing = tmp_path / "missing.owl"
    completed = invoke(*mode, "--ontology", str(missing))
    assert completed.returncode == 2
    assert "no ontology files" in completed.stderr
