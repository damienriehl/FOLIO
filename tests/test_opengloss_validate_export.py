"""Offline checks of mapping validation, annotation export, and gold scoring."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, SKOS

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from opengloss_mapping import owl_export, score, validate

FIXTURES = Path(__file__).parent / "fixtures" / "opengloss" / "validate"
SCRIPTS = Path(__file__).parents[1] / "scripts"


def test_valid_mapping():
    header, rows = validate.read_mapping_set(FIXTURES / "mappings.tsv")
    assert len(rows) == 6
    assert validate.validate(header, rows, FIXTURES / "folio.owl") == []


@pytest.mark.parametrize(("code", "old", "new"), [
    ("header-missing-key", "# mapping_set_title: OpenGloss fixture", "# mapping_set_title:"),
    ("curie-map", "OGL:headword", "unknown:headword"),
    ("columns", "subject_id\tsubject_label", "subject_id\twrong_label"),
    ("predicate", "skos:broadMatch", "owl:sameAs"),
    ("forbidden", "Handwritten offline test mappings", "contains openGlossID"),
    ("object-id", "OGS:agreement:noun:0", "OGS:agreement:noun:0|agreement:noun:1"),
    ("subject-id", "FOLIO:A", "FOLIO:A:bad"),
    ("confidence", "0.700", "nan"),
    ("justification", "semapv:LexicalMatching", "rdfs:label"),
    ("order", "FOLIO:A\tAgreement\tskos:broadMatch", "FOLIO:B\tAgreement\tskos:broadMatch"),
    ("duplicate", "OGS:agreement:noun:1", "OGS:agreement:noun:0"),
    ("folio-subject", "FOLIO:B", "FOLIO:C"),
])
def test_findings(tmp_path, code, old, new):
    path = tmp_path / "mutated.tsv"
    path.write_text((FIXTURES / "mappings.tsv").read_text().replace(old, new), encoding="utf-8")
    header, rows = validate.read_mapping_set(path)
    assert code in {f.code for f in validate.validate(header, rows, FIXTURES / "folio.owl")}


@pytest.mark.parametrize("value", ["owl:sameAs", "owl:equivalentClass", "owl#sameAs", "OWL#EQUIVALENTCLASS", "OPENGLOSSID"])
def test_forbidden_anywhere(tmp_path, value):
    path = tmp_path / "bad.tsv"
    path.write_text((FIXTURES / "mappings.tsv").read_text() + "# " + value + "\n")
    header, rows = validate.read_mapping_set(path)
    assert "forbidden" in {f.code for f in validate.validate(header, rows)}


@pytest.mark.parametrize("value", ["0", "-1", "1.01", "inf", "-inf", "", "nonsense"])
def test_confidence_bounds(value):
    header, rows = validate.read_mapping_set(FIXTURES / "mappings.tsv")
    rows[0]["confidence"] = value
    assert "confidence" in {f.code for f in validate.validate(header, rows)}


def test_export(tmp_path):
    first, second = tmp_path / "one.ttl", tmp_path / "two.ttl"
    count = owl_export.export(FIXTURES / "mappings.tsv", FIXTURES / "senses.tsv", first)
    owl_export.export(FIXTURES / "mappings.tsv", FIXTURES / "senses.tsv", second)
    assert first.read_bytes() == second.read_bytes()
    graph = Graph().parse(first, format="turtle")
    assert len(graph) == count
    header, rows = validate.read_mapping_set(FIXTURES / "mappings.tsv")
    expand = lambda curie: URIRef(header["curie_map"][curie.split(":", 1)[0]] + curie.split(":", 1)[1])
    predicates = {expand(p) for p in validate.PREDICATES}
    assert sum(1 for _, p, _ in graph if p in predicates) == 6
    assert len(set(graph.subjects(RDF.type, OWL.Axiom))) == 6
    ontolex = Namespace("http://www.w3.org/ns/lemon/ontolex#")
    assert set(graph.subject_objects(ontolex.reference)) == {
        (expand(row["object_id"]), expand(row["subject_id"])) for row in rows if row["predicate_id"] == "skos:exactMatch"
    }
    assert len(set(graph.subjects(RDF.type, ontolex.LexicalSense))) == 6
    for row in rows:
        subject, predicate, obj = (expand(row[k]) for k in ("subject_id", "predicate_id", "object_id"))
        assert (subject, predicate, obj) in graph
        axiom = next(graph.subjects(OWL.annotatedTarget, obj))
        assert (axiom, OWL.annotatedSource, subject) in graph
        assert (axiom, OWL.annotatedProperty, predicate) in graph
        assert next(graph.objects(axiom, Namespace("https://w3id.org/sssom/").confidence)).datatype == URIRef("http://www.w3.org/2001/XMLSchema#double")
        assert next(graph.objects(obj, SKOS.definition)).language == "en"
        lexeme = graph.value(obj, ontolex.isSenseOf)
        assert (lexeme, ontolex.sense, obj) in graph
        assert graph.value(graph.value(lexeme, ontolex.canonicalForm), ontolex.writtenRep).language == "en"
    ontology = URIRef(header["mapping_set_id"])
    assert (ontology, RDF.type, OWL.Ontology) in graph
    assert (ontology, OWL.versionIRI, URIRef(str(ontology) + "/0.1.0")) in graph
    assert not list(graph.triples((None, OWL.imports, None)))


def test_missing_sense(tmp_path):
    senses = tmp_path / "senses.tsv"
    senses.write_text((FIXTURES / "senses.tsv").read_text().replace("agreement:noun:0", "other:noun:0"))
    with pytest.raises(ValueError, match="agreement:noun:0"):
        owl_export.export(FIXTURES / "mappings.tsv", senses, tmp_path / "out.ttl")


def test_score():
    _, rows = validate.read_mapping_set(FIXTURES / "mappings.tsv")
    result = score.score(rows, score.read_gold(FIXTURES / "gold.tsv"))
    assert {key: result[key] for key in ("judged", "emitted_judged", "precision", "recall", "predicate_agreement", "rows")} == {
        "judged": 5, "emitted_judged": 4, "precision": 0.75, "recall": 0.75, "predicate_agreement": 0.5, "rows": 6,
    }
    assert result["rows_by_predicate"]["skos:exactMatch"] == 2
    assert score.score([], [])["precision"] is None
    assert score.score([], [])["recall"] is None
    assert score.score([], [])["predicate_agreement"] is None


def test_clis(tmp_path):
    def run(name, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)], capture_output=True, text=True)
    result = run("validate_opengloss_mappings.py", FIXTURES / "mappings.tsv", "--folio", FIXTURES / "folio.owl")
    assert result.returncode == 0 and "OK: 6 rows" in result.stdout
    result = run("export_opengloss_owl.py", FIXTURES / "mappings.tsv", "--senses", FIXTURES / "senses.tsv", "--out", tmp_path / "out.ttl")
    assert result.returncode == 0 and "triples" in result.stdout
    result = run("score_opengloss_mappings.py", FIXTURES / "mappings.tsv", "--gold", FIXTURES / "gold.tsv", "--json")
    assert result.returncode == 0 and json.loads(result.stdout)["precision"] == 0.75
    bad = tmp_path / "bad.tsv"
    bad.write_text((FIXTURES / "mappings.tsv").read_text().replace("0.700", "0"))
    result = run("validate_opengloss_mappings.py", bad)
    assert result.returncode == 1 and "confidence:" in result.stdout and "FAIL:" in result.stdout


def test_curie_expansions_and_missing_subject():
    header, rows = validate.read_mapping_set(FIXTURES / "mappings.tsv")
    header["curie_map"]["OGS"] = "https://wrong.example/"
    assert "curie-map" in {f.code for f in validate.validate(header, rows)}
    header["curie_map"]["OGS"] = validate.CURIE_MAP["OGS"]
    rows[0]["subject_id"] = "FOLIO:missing"
    assert "folio-subject" in {f.code for f in validate.validate(header, rows, FIXTURES / "folio.owl")}


@pytest.mark.parametrize("change", ["extra", "missing", "empty"])
def test_malformed_columns(tmp_path, change):
    text = (FIXTURES / "mappings.tsv").read_text()
    if change == "extra":
        text = text.replace("head-word score=0.7", "head-word score=0.7\textra")
    elif change == "missing":
        text = text.replace("\tagreement\thead-word score=0.7", "")
    else:
        text = "\n".join(line for line in text.splitlines() if line.startswith("#"))
    path = tmp_path / "malformed.tsv"
    path.write_text(text)
    header, rows = validate.read_mapping_set(path)
    assert "columns" in {f.code for f in validate.validate(header, rows)}


def test_score_rounding_and_no_correct():
    _, rows = validate.read_mapping_set(FIXTURES / "mappings.tsv")
    gold = [dict(subject_id=row["subject_id"], object_id=row["object_id"],
                 verdict="correct" if index == 0 else "incorrect",
                 expected_predicate="", note="") for index, row in enumerate(rows[:3])]
    assert score.score(rows, gold)["precision"] == 0.3333
    assert score.score([], gold)["recall"] == 0.0
    gold[0]["verdict"] = "incorrect"
    result = score.score(rows, gold)
    assert result["precision"] == 0.0 and result["recall"] is None


@pytest.mark.parametrize("change", ["verdict", "duplicate"])
def test_invalid_gold(tmp_path, change):
    text = (FIXTURES / "gold.tsv").read_text()
    if change == "verdict":
        text = text.replace("\tcorrect\t", "\tmaybe\t")
    else:
        text += text.splitlines()[-1] + "\n"
    path = tmp_path / "gold.tsv"
    path.write_text(text)
    with pytest.raises(ValueError):
        score.read_gold(path)


def test_mapping_set_id_is_pinned():
    header, rows = validate.read_mapping_set(FIXTURES / 'mappings.tsv')
    header['mapping_set_id'] = 'https://example.org/wrong-set'
    assert 'mapping-set-id' in {finding.code for finding in validate.validate(header, rows)}


def test_quotes_round_trip_through_writer_validator_exporter(tmp_path):
    from opengloss_mapping.senses import Sense
    from opengloss_mapping.sssom_writer import write_sssom, write_senses, write_gaps
    header, original = validate.read_mapping_set(FIXTURES / 'mappings.tsv')
    label = 'The "Agreement"'
    gloss = 'An agreement called a "contract", with "quoted" terms.'
    row = dict(original[0], subject_label=label, object_label='"Agreement"')
    sense = Sense(row['object_id'].removeprefix('OGS:'), 'agreement:noun',
                  '"Agreement"', 'noun', 0, 'law_government', 'law_government', gloss)
    mapping, sidecar, turtle, gaps = [tmp_path / name for name in ('m.tsv', 's.tsv', 'm.ttl', 'g.tsv')]
    write_sssom(mapping, header, [row])
    write_senses(sidecar, [sense], [row])
    write_gaps(gaps, [dict(subject_id=row['subject_id'], subject_label=label,
                           match_string='"agreement"', headword_senses_domains='a="domain"')])
    parsed_header, rows = validate.read_mapping_set(mapping)
    assert rows == [row]
    assert validate.validate(parsed_header, rows) == []
    owl_export.export(mapping, sidecar, turtle)
    graph = Graph().parse(turtle, format='turtle')
    obj = URIRef(header['curie_map']['OGS'] + sense.sense_id)
    assert str(graph.value(obj, SKOS.definition)) == gloss
    import csv
    with gaps.open() as stream:
        assert next(csv.DictReader(stream, delimiter='\t', quoting=csv.QUOTE_NONE))['subject_label'] == label
    for path in (mapping, sidecar, gaps):
        assert '""' not in path.read_text()


def test_writer_rejects_a_delimiter_that_survives_cleaning(tmp_path, monkeypatch):
    from opengloss_mapping import sssom_writer
    monkeypatch.setattr(sssom_writer, 'clean', str)
    gap = dict(subject_id='FOLIO:A', subject_label='bad\tlabel', match_string='a', headword_senses_domains='')
    with pytest.raises(ValueError, match='delimiter|control'):
        sssom_writer.write_gaps(tmp_path / 'g.tsv', [gap])
