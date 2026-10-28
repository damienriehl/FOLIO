import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from rdflib import BNode, Graph, Literal, Namespace, OWL, RDF, RDFS, SKOS, URIRef


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
sys.path.insert(0, str(EXAMPLES))

from labels_and_hierarchy import inspect_class  # noqa: E402
from load_and_inspect import load_graph, summarize  # noqa: E402
from query_classes import query_classes  # noqa: E402


EX = Namespace("https://example.test/")


def fixture_graph() -> Graph:
    graph = Graph()
    for subject in (EX.Child, EX.ParentA, EX.Unlabeled):
        graph.add((subject, RDF.type, OWL.Class))
    graph.add((EX.property, RDF.type, RDF.Property))
    graph.add((EX.property, RDFS.label, Literal("Not a class")))
    graph.add((BNode(), RDF.type, OWL.Class))
    graph.add((EX.Child, RDFS.subClassOf, EX.ParentA))
    graph.add((EX.Child, RDFS.subClassOf, EX.ParentB))
    graph.add((EX.ParentA, RDFS.subClassOf, EX.Grandparent))
    graph.add((EX.Grandchild, RDFS.subClassOf, EX.Child))
    graph.add((EX.Child, RDFS.subClassOf, BNode()))
    graph.add((EX.Child, RDFS.label, Literal("Café", lang="fr-CA")))
    graph.add((EX.Child, SKOS.altLabel, Literal("Child")))
    graph.add((EX.Child, SKOS.hiddenLabel, Literal("typed", datatype=EX.kind)))
    graph.add((EX.Child, SKOS.prefLabel, EX.not_a_literal))
    graph.add((EX.Child, OWL.deprecated, Literal(True)))
    return graph


@pytest.fixture()
def ontology_file(tmp_path: Path) -> Path:
    path = tmp_path / "fixture.owl"
    fixture_graph().serialize(path, format="xml")
    return path


def run_script(name: str, *args: object, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(EXAMPLES / name), *(str(arg) for arg in args)],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_summary_counts_only_explicit_named_classes_and_bounds_sample() -> None:
    result = summarize(fixture_graph(), sample_limit=2)
    assert result["declared_named_class_count"] == 3
    assert result["class_iri_sample"] == [str(EX.Child), str(EX.ParentA)]


def test_loader_preserves_bytes_and_rejects_urls(ontology_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = hashlib.sha256(ontology_file.read_bytes()).digest()
    monkeypatch.setattr("socket.socket.connect", lambda *_: pytest.fail("network attempted"))
    assert len(load_graph(ontology_file)) > 0
    assert hashlib.sha256(ontology_file.read_bytes()).digest() == before
    with pytest.raises(ValueError, match="local filesystem path"):
        load_graph("https://example.test/ontology.owl")


def test_loader_cli_handles_cwd_missing_and_malformed_inputs(ontology_file: Path, tmp_path: Path) -> None:
    success = run_script("load_and_inspect.py", ontology_file, cwd=tmp_path)
    assert success.returncode == 0
    assert json.loads(success.stdout)["declared_named_class_count"] == 3

    for bad_path in (tmp_path / "missing.owl", tmp_path / "bad.owl"):
        if bad_path.name == "bad.owl":
            bad_path.write_text("not RDF/XML", encoding="utf-8")
        failed = run_script("load_and_inspect.py", bad_path)
        assert failed.returncode != 0
        assert not failed.stdout
        assert "could not load ontology" in failed.stderr


def test_default_ontology_is_script_relative(tmp_path: Path) -> None:
    result = run_script("load_and_inspect.py", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["declared_named_class_count"] > 0


def test_inspection_preserves_terms_and_only_direct_named_neighbors() -> None:
    result = inspect_class(fixture_graph(), str(EX.Child))
    assert [item["iri"] for item in result["direct_parents"]] == [str(EX.ParentA), str(EX.ParentB)]
    assert [item["iri"] for item in result["direct_children"]] == [str(EX.Grandchild)]
    labels = result["labels"]
    assert any(item.get("language") == "fr-CA" and item["value"] == "Café" for item in labels)
    assert any(item.get("datatype") == str(EX.kind) for item in labels)
    assert any(item["term_kind"] == "iri" for item in labels)
    assert result["deprecated"][0]["value"] == "true"
    assert result["direct_parents"][0]["deprecated"] == []


def test_inspection_accepts_unlabeled_and_rejects_invalid_subjects() -> None:
    graph = fixture_graph()
    assert inspect_class(graph, str(EX.Unlabeled))["labels"] == []
    for value in ("", "relative", str(EX.unknown), str(EX.property)):
        with pytest.raises(ValueError):
            inspect_class(graph, value)


def test_query_is_direct_deterministic_bounded_and_keeps_unlabeled() -> None:
    graph = fixture_graph()
    rows = query_classes(graph)
    assert any(row["iri"] == str(EX.Unlabeled) and row["label"] is None for row in rows)
    assert not any(row["iri"] == str(EX.property) for row in rows)
    assert [row["iri"] for row in query_classes(graph, str(EX.ParentA))] == [str(EX.Child)]
    assert query_classes(graph, str(EX.Grandparent)) == [
        {"iri": str(EX.ParentA), "label": None, "deprecated": None}
    ]
    assert query_classes(graph, str(EX.unknown)) == []

    for index in range(25):
        graph.add((EX.Many, RDFS.label, Literal(f"label {index:02}")))
    graph.add((EX.Many, RDF.type, OWL.Class))
    first = query_classes(graph)
    assert first == query_classes(graph)
    assert len(first) == 20


def test_inspect_and_query_clis_from_another_working_directory(ontology_file: Path, tmp_path: Path) -> None:
    before = ontology_file.read_bytes()
    inspected = run_script(
        "labels_and_hierarchy.py", str(EX.Child), "--ontology", ontology_file, cwd=tmp_path
    )
    queried = run_script(
        "query_classes.py", "--ontology", ontology_file, "--parent", str(EX.ParentA), cwd=tmp_path
    )
    assert inspected.returncode == queried.returncode == 0
    assert json.loads(inspected.stdout)["iri"] == str(EX.Child)
    assert json.loads(queried.stdout)["row_count"] == 1
    assert ontology_file.read_bytes() == before


def test_published_investment_funds_relation_and_real_query() -> None:
    graph = load_graph(ROOT / "FOLIO.owl")
    parent = "https://folio.openlegalstandard.org/RCzxVprwB3RwZ8EMewt18Jt"
    child = "https://folio.openlegalstandard.org/R1cNH7TLMiSlSbIbdFsynUk"
    inspected = inspect_class(graph, parent)
    assert child in [item["iri"] for item in inspected["direct_children"]]
    assert child in [row["iri"] for row in query_classes(graph, parent)]
