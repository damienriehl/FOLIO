"""Export validated SSSOM mappings as an OWL/SKOS/OntoLex annotation module."""
from __future__ import annotations

import csv
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD

from .validate import read_mapping_set, validate

ONTOLEX = Namespace("http://www.w3.org/ns/lemon/ontolex#")
SSSOM = Namespace("https://w3id.org/sssom/")


def export(tsv_path: str | Path, senses_path: str | Path, out_path: str | Path) -> int:
    """Write deterministic Turtle and return the graph's triple count."""
    header, rows = read_mapping_set(tsv_path)
    findings = validate(header, rows)
    if findings:
        raise ValueError("Invalid mapping set: " + "; ".join(f"{f.code}: {f.message}" for f in findings))
    with Path(senses_path).open(encoding="utf-8", newline="") as handle:
        senses = {row["sense_id"]: row for row in csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)}
    missing = sorted({row["object_id"][4:] for row in rows} - senses.keys())
    if missing:
        raise ValueError("Mapped sense missing from senses.tsv: " + ", ".join(missing))
    graph = Graph()
    for prefix, expansion in header["curie_map"].items():
        graph.bind(prefix, Namespace(expansion), replace=True)
    for prefix, namespace in {"owl": OWL, "rdfs": RDFS, "dcterms": DCTERMS, "ontolex": ONTOLEX, "sssom": SSSOM, "xsd": XSD}.items():
        graph.bind(prefix, namespace, replace=True)
    def expand(curie: str) -> URIRef:
        prefix, local = curie.split(":", 1)
        return URIRef(header["curie_map"][prefix] + local)
    ontology = URIRef(header["mapping_set_id"])
    graph.add((ontology, RDF.type, OWL.Ontology))
    graph.add((ontology, OWL.versionIRI, URIRef(str(ontology) + "/" + str(header["mapping_set_version"]))))
    graph.add((ontology, OWL.versionInfo, Literal(str(header["mapping_set_version"]))))
    graph.add((ontology, DCTERMS.license, URIRef(header["license"])))
    for source in ("subject_source", "object_source"):
        graph.add((ontology, DCTERMS.source, URIRef(header[source])))
    graph.add((ontology, DCTERMS.created, Literal(str(header["mapping_date"]), datatype=XSD.date)))
    graph.add((ontology, RDFS.comment, Literal("The OGS and OGL namespaces are provisional tag URIs owned by FOLIO; they are not official OpenGloss namespaces.", lang="en")))
    for index, row in enumerate(rows):
        subject, predicate, obj = (expand(row[key]) for key in ("subject_id", "predicate_id", "object_id"))
        graph.add((subject, predicate, obj))
        axiom = BNode(f"axiom{index:09d}")
        for prop, target in ((RDF.type, OWL.Axiom), (OWL.annotatedSource, subject),
                             (OWL.annotatedProperty, predicate), (OWL.annotatedTarget, obj),
                             (SSSOM.confidence, Literal(float(row["confidence"]), datatype=XSD.double)),
                             (SSSOM.mapping_justification, expand(row["mapping_justification"])),
                             (RDFS.comment, Literal(row["comment"]))):
            graph.add((axiom, prop, target))
        sense = senses[row["object_id"][4:]]
        lexeme = expand("OGL:" + sense["lexeme_id"])
        form = URIRef(str(lexeme) + "#form")
        graph.add((obj, RDF.type, ONTOLEX.LexicalSense))
        graph.add((obj, SKOS.definition, Literal(sense["gloss"], lang="en")))
        graph.add((obj, ONTOLEX.isSenseOf, lexeme))
        graph.add((lexeme, RDF.type, ONTOLEX.LexicalEntry))
        graph.add((lexeme, ONTOLEX.sense, obj))
        graph.add((lexeme, ONTOLEX.canonicalForm, form))
        graph.add((form, ONTOLEX.writtenRep, Literal(sense["headword"], lang="en")))
        if predicate == SKOS.exactMatch:
            graph.add((obj, ONTOLEX.reference, subject))
    # Fully expanded N-Triples statements are also Turtle. Sort them explicitly;
    # stable axiom IDs and skolem forms avoid serializer-dependent bnode ordering.
    prefixes = "".join(f"@prefix {prefix}: <{namespace}> .\n" for prefix, namespace in sorted(graph.namespaces()))
    statements = sorted(graph.serialize(format="nt").splitlines(keepends=True))
    Path(out_path).write_text(prefixes + "\n" + "".join(statements), encoding="utf-8")
    return len(graph)
