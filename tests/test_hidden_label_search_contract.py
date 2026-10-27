"""Producer checks for the portable hidden-label search acceptance contract."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDFS, SKOS, XSD

ROOT = Path(__file__).parents[1]
CASES_PATH = ROOT / "qa/ontology/search/hidden-label-cases.json"
FIXTURE_PATH = ROOT / "qa/ontology/search/hidden-label-fixture.owl"
AGREEMENTS = URIRef("https://folio.openlegalstandard.org/R88D8i8AcSTUig2X3yPbFHg")
OBLIGATION = URIRef("https://folio.openlegalstandard.org/RDtFkLR3v97fran5zQ3ugao")
INDENTURE = URIRef("https://folio.openlegalstandard.org/R8NLKPDCyexTiBJCz8mdsjz")
REQUIRED_HIDDEN = {"Accord", "Accords", "Pact", "Pacts", "Compact", "Compacts"}
EXCLUDED_HIDDEN = {
    "Covenant", "Covenants", "Indenture", "Indentures",
    "Concordat", "Concordats", "Undertaking", "Undertakings",
    "Agreement", "Contract",
}
SUPPORTED_PREDICATES = {str(RDFS.label), str(SKOS.prefLabel), str(SKOS.altLabel), str(SKOS.hiddenLabel)}

sys.path.insert(0, str(ROOT / "scripts"))
from generate_webprotege_merge import apply_changes, compute_semantic_diff


def load_contract() -> dict:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def literal_for(case: dict) -> Literal:
    if case["language"]:
        return Literal(case["lexical_form"], lang=case["language"])
    if case["datatype"]:
        return Literal(case["lexical_form"], datatype=URIRef(case["datatype"]))
    return Literal(case["lexical_form"])


def equivalent_literal(graph: Graph, subject: URIRef, predicate: URIRef, expected: Literal) -> bool:
    """Match RDF 1.1 strings while retaining language and other datatype identity."""
    values = set(graph.objects(subject, predicate))
    if expected in values:
        return True
    if expected.language or expected.datatype:
        return False
    return Literal(str(expected), datatype=XSD.string) in values


def validate_contract(contract: dict) -> None:
    assert contract["schema_version"] == 1
    assert isinstance(contract.get("source_revision"), str) and len(contract["source_revision"]) == 40
    cases = contract.get("cases")
    assert cases, "the acceptance case table must not be empty"
    ids = [case.get("case_id") for case in cases]
    assert all(ids), "every acceptance case needs a case_id"
    assert len(ids) == len(set(ids)), "acceptance case IDs must be unique"
    for case in cases:
        assert case["predicate"] in SUPPORTED_PREDICATES, f"unsupported predicate in {case['case_id']}"
        assert case.get("target_iri", "").startswith("https://folio.openlegalstandard.org/")
        assert case["query"] == case["lexical_form"]
        assert case["producer_expected"] is True
        assert case["consumer_expected"]["result_count"] == 1
    hidden = {
        case["lexical_form"] for case in cases
        if case["target_iri"] == str(AGREEMENTS) and case["predicate"] == str(SKOS.hiddenLabel)
    }
    assert hidden == REQUIRED_HIDDEN, "case table must pin exactly the six approved hidden aliases"


def assert_graph_contract(graph: Graph, contract: dict, artifact: str) -> None:
    for case in contract["cases"]:
        subject = URIRef(case["target_iri"])
        predicate = URIRef(case["predicate"])
        assert equivalent_literal(graph, subject, predicate, literal_for(case)), (
            f"{artifact}: missing or changed case {case['case_id']}"
        )
    actual_hidden = {str(value) for value in graph.objects(AGREEMENTS, SKOS.hiddenLabel)}
    assert not (actual_hidden & EXCLUDED_HIDDEN), f"{artifact}: excluded Agreements hidden label"
    assert REQUIRED_HIDDEN <= actual_hidden, f"{artifact}: incomplete Agreements hidden labels"


def test_case_inventory_is_complete_and_independent():
    contract = load_contract()
    validate_contract(contract)
    sentinels = {
        case["lexical_form"] for case in contract["cases"]
        if case["consumer_expected"].get("hidden_only_sentinel")
    }
    assert sentinels == {"Pact", "Compact"}


@pytest.mark.parametrize("mutation", ["empty", "duplicate", "missing", "predicate", "iri"])
def test_invalid_case_inventory_fails_explicitly(mutation):
    contract = copy.deepcopy(load_contract())
    if mutation == "empty":
        contract["cases"] = []
    elif mutation == "duplicate":
        contract["cases"][1]["case_id"] = contract["cases"][0]["case_id"]
    elif mutation == "missing":
        contract["cases"] = [case for case in contract["cases"] if case["query"] != "Pact"]
    elif mutation == "predicate":
        contract["cases"][0]["predicate"] = "https://example.test/unsupported"
    else:
        contract["cases"][0]["target_iri"] = ""
    with pytest.raises((AssertionError, KeyError)):
        validate_contract(contract)


def test_fixture_preserves_language_identity_and_precision_controls():
    graph = Graph().parse(FIXTURE_PATH)
    assert_graph_contract(graph, load_contract(), "hidden-label-fixture.owl")
    assert Literal("Accords") in graph.objects(AGREEMENTS, SKOS.hiddenLabel)
    assert Literal("Accords", lang="fr-fr") in graph.objects(AGREEMENTS, SKOS.altLabel)
    assert Literal("Covenant") in graph.objects(OBLIGATION, SKOS.prefLabel)
    assert Literal("Indenture") in graph.objects(INDENTURE, RDFS.label)
    for sentinel in ("Pact", "Compact"):
        assert Literal(sentinel) not in graph.objects(AGREEMENTS, SKOS.altLabel)
        assert Literal(sentinel) not in graph.objects(AGREEMENTS, SKOS.prefLabel)
        assert Literal(sentinel) not in graph.objects(AGREEMENTS, RDFS.label)


@pytest.mark.parametrize("artifact", ["FOLIO.owl", "FOLIO-webprotege-merge-output.owl"])
def test_committed_ontology_artifact_matches_contract(artifact):
    graph = Graph().parse(ROOT / artifact)
    assert_graph_contract(graph, load_contract(), artifact)


def test_output_check_identifies_artifact_and_case():
    graph = Graph().parse(FIXTURE_PATH)
    graph.remove((AGREEMENTS, SKOS.hiddenLabel, Literal("Pact")))
    with pytest.raises(AssertionError, match=r"temporary-output\.owl: missing or changed case agreements-hidden-pact"):
        assert_graph_contract(graph, load_contract(), "temporary-output.owl")


@pytest.mark.parametrize("mutation", ["language", "owner", "excluded"])
def test_precision_mutations_fail_without_contaminating_fixture(mutation):
    graph = Graph().parse(FIXTURE_PATH)
    if mutation == "language":
        graph.remove((AGREEMENTS, SKOS.hiddenLabel, Literal("Compact")))
        graph.add((AGREEMENTS, SKOS.hiddenLabel, Literal("Compact", lang="en")))
    elif mutation == "owner":
        graph.remove((AGREEMENTS, SKOS.hiddenLabel, Literal("Compact")))
        graph.add((OBLIGATION, SKOS.hiddenLabel, Literal("Compact")))
    else:
        graph.add((AGREEMENTS, SKOS.hiddenLabel, Literal("Covenant")))
    with pytest.raises(AssertionError):
        assert_graph_contract(graph, load_contract(), f"{mutation}-mutation.owl")

    pristine = Graph().parse(FIXTURE_PATH)
    assert_graph_contract(pristine, load_contract(), "hidden-label-fixture.owl")


def test_merge_restores_hidden_labels_and_is_idempotent(tmp_path):
    source = FIXTURE_PATH.read_text(encoding="utf-8")
    baseline = source
    for label in REQUIRED_HIDDEN:
        baseline = baseline.replace(f"        <skos:hiddenLabel>{label}</skos:hiddenLabel>\n", "")

    source_path = tmp_path / "source.owl"
    source_path.write_text(source, encoding="utf-8")
    diff = compute_semantic_diff(str(source_path), baseline)
    assert set(diff.new_hidden_labels[str(AGREEMENTS)]) == {Literal(label) for label in REQUIRED_HIDDEN}

    output = apply_changes(baseline, diff, source)
    assert_graph_contract(Graph().parse(data=output, format="xml"), load_contract(), "merge-output.owl")
    second = compute_semantic_diff(str(source_path), output)
    assert not second.new_hidden_labels
    assert not second.new_alt_labels
    assert not second.removed_labels
    assert apply_changes(output, second, source) == output
