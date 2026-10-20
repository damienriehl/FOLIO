from __future__ import annotations

import sys
from pathlib import Path

import pytest
from rdflib.namespace import SKOS

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from ontology_qa.corrections import apply_correction_batch, make_correction

RID = "a" * 64
SUBJECT = "https://example.test/C"


def ontology(value="Old &amp; wrong", extra="") -> str:
    return f"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
 xmlns:owl="http://www.w3.org/2002/07/owl#"
 xmlns:skos="http://www.w3.org/2004/02/skos/core#">
<owl:Class rdf:about="{SUBJECT}">
  <rdfs:label>Concept</rdfs:label>
  <skos:definition xml:lang="en">{value}</skos:definition>
  {extra}
</owl:Class>
</rdf:RDF>"""


def correction(before="Old & wrong", replacement='New "correct" value'):
    return make_correction(
        root_record_id=RID, subject=SUBJECT, predicate=str(SKOS.definition),
        language="en", datatype=None, before=before, replacement=replacement,
        proposer_route="proposer", verifier_routes=["v1", "v2"],
        verifier_qualification_hashes=["1" * 64, "2" * 64],
    )


def write_source(tmp_path, text=None):
    source = tmp_path / "source.owl"
    source.write_text(text or ontology(), encoding="utf-8")
    return source


def test_exact_verified_replacement_applies_once_and_emits_ledger(tmp_path):
    source, output = write_source(tmp_path), tmp_path / "output.owl"
    result = apply_correction_batch(source, output, [correction()])
    assert result["correction_count"] == 1
    assert "New &quot;correct&quot; value" in output.read_text()
    assert source.read_text() == ontology()


@pytest.mark.parametrize("before", ["missing", "changed old value"])
def test_zero_match_or_stale_hash_publishes_nothing(tmp_path, before):
    source, output = write_source(tmp_path), tmp_path / "output.owl"
    with pytest.raises(ValueError):
        apply_correction_batch(source, output, [correction(before=before)])
    assert not output.exists()
    assert source.read_text() == ontology()


def test_multiple_matches_publish_nothing(tmp_path):
    source = write_source(tmp_path, ontology(extra='<skos:definition xml:lang="en">Old &amp; wrong</skos:definition>'))
    output = tmp_path / "output.owl"
    with pytest.raises(ValueError, match="exactly one"):
        apply_correction_batch(source, output, [correction()])
    assert not output.exists()


def test_proposer_cannot_verify_own_candidate():
    with pytest.raises(ValueError, match="excluding proposer"):
        make_correction(
            root_record_id=RID, subject=SUBJECT, predicate=str(SKOS.definition),
            language="en", datatype=None, before="a", replacement="b",
            proposer_route="same", verifier_routes=["same", "other"],
            verifier_qualification_hashes=["1" * 64, "2" * 64],
        )


def test_repeated_revision_is_rejected_atomically(tmp_path):
    source, output = write_source(tmp_path), tmp_path / "output.owl"
    item = correction()
    with pytest.raises(ValueError, match="repeated"):
        apply_correction_batch(source, output, [item, item])
    assert not output.exists()


def test_correction_cycle_is_rejected_atomically(tmp_path):
    source, output = write_source(tmp_path), tmp_path / "output.owl"
    first = correction(replacement="Intermediate")
    second = make_correction(
        root_record_id=RID, subject=SUBJECT, predicate=str(SKOS.definition),
        language="en", datatype=None, before="Intermediate", replacement="Old & wrong",
        proposer_route="proposer", verifier_routes=["v1", "v2"],
        verifier_qualification_hashes=["1" * 64, "2" * 64],
    )
    with pytest.raises(ValueError, match="repeats"):
        apply_correction_batch(source, output, [first, second])
    assert not output.exists()


def test_xml_entity_encoded_apostrophe_is_located(tmp_path):
    source = tmp_path / "source.owl"
    output = tmp_path / "output.owl"
    source.write_text(
        ontology("Owner&apos;s old value"), encoding="utf-8"
    )
    item = correction(
        before="Owner's old value", replacement="Owner's corrected value"
    )
    apply_correction_batch(source, output, [item])
    assert "Owner&apos;s corrected value" in output.read_text(encoding="utf-8")
