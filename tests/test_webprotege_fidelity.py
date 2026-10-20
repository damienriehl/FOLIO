from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from ontology_qa.delta import build_hydration_manifest
from ontology_qa.fidelity import verify_merge_fidelity


PREFIX = """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:skos="http://www.w3.org/2004/02/skos/core#">
<rdf:Description rdf:about="https://example.test/C">"""
SUFFIX = "</rdf:Description></rdf:RDF>"


def owl(label: str, extra: str = "") -> str:
    return (
        PREFIX
        + f'<skos:altLabel xml:lang="en">{label}</skos:altLabel>'
        + extra
        + SUFFIX
    )


def setup_case(tmp_path: Path):
    baseline = tmp_path / "baseline.owl"
    candidate = tmp_path / "candidate.owl"
    baseline.write_text(owl("Old"), encoding="utf-8")
    candidate.write_text(owl("New"), encoding="utf-8")
    manifest = build_hydration_manifest(
        baseline, candidate, run_id="run", attempt_id="1"
    )
    states = {
        record["record_id"]: "accepted"
        for record in manifest["payload"]["records"]
    }
    return baseline, candidate, manifest, states


def test_exact_accepted_graph_change_passes(tmp_path):
    baseline, candidate, manifest, states = setup_case(tmp_path)
    result = verify_merge_fidelity(
        webprotege_base_path=baseline,
        merge_output_path=candidate,
        manifest=manifest,
        accepted_states=states,
    )
    assert result["verified"] is True
    assert result["accepted_record_count"] == 1


def test_stale_or_missing_accepted_change_fails(tmp_path):
    baseline, _, manifest, states = setup_case(tmp_path)
    with pytest.raises(ValueError, match="stale"):
        verify_merge_fidelity(
            webprotege_base_path=baseline,
            merge_output_path=baseline,
            manifest=manifest,
            accepted_states=states,
        )


def test_unrelated_graph_change_fails(tmp_path):
    baseline, _, manifest, states = setup_case(tmp_path)
    output = tmp_path / "output.owl"
    output.write_text(
        owl(
            "New",
            '<skos:hiddenLabel xml:lang="en">Unreviewed</skos:hiddenLabel>',
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unrelated"):
        verify_merge_fidelity(
            webprotege_base_path=baseline,
            merge_output_path=output,
            manifest=manifest,
            accepted_states=states,
        )


def test_incomplete_or_nonaccepted_ledger_fails(tmp_path):
    baseline, candidate, manifest, states = setup_case(tmp_path)
    record_id = next(iter(states))
    with pytest.raises(ValueError, match="not accepted"):
        verify_merge_fidelity(
            webprotege_base_path=baseline,
            merge_output_path=candidate,
            manifest=manifest,
            accepted_states={record_id: "quarantined"},
        )
