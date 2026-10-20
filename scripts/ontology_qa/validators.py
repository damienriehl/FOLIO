"""Deterministic annotation census and validation."""

from __future__ import annotations

import ast
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import langcodes
import yaml
from pyshacl import validate as shacl_validate
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

TARGET_PREDICATES = {
    RDFS.label,
    SKOS.prefLabel,
    SKOS.altLabel,
    SKOS.hiddenLabel,
    SKOS.definition,
    SKOS.example,
    SKOS.note,
}
TARGET_XML_NAMES = {
    f"{{{str(predicate).rsplit('#', 1)[0]}#}}{str(predicate).rsplit('#', 1)[1]}"
    for predicate in TARGET_PREDICATES
}
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    subject: str
    predicate: str
    message: str


def load_policy(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _looks_serialized_container(value: str) -> bool:
    stripped = value.strip()
    if len(stripped) < 2 or stripped[0] not in "[{(" or stripped[-1] not in "]})":
        return False
    try:
        parsed = ast.literal_eval(stripped)
    except (SyntaxError, ValueError):
        return False
    return isinstance(parsed, (list, tuple, set, dict))


def _script_risk(value: str, language: str) -> bool:
    expected = {
        "ar": "ARABIC",
        "el": "GREEK",
        "he": "HEBREW",
        "ru": "CYRILLIC",
        "uk": "CYRILLIC",
        "zh": "CJK",
    }.get(language.split("-")[0])
    if not expected:
        return False
    letters = [unicodedata.name(char, "") for char in value if char.isalpha()]
    return bool(letters) and not any(expected in name for name in letters)


def _valid_language_tag(language: str) -> bool:
    return "_" not in language and langcodes.tag_is_valid(language)


def validate_ontology(
    ontology_path: str | Path,
    *,
    policy_path: str | Path,
    shapes_path: str | Path,
) -> dict[str, Any]:
    path = Path(ontology_path)
    policy = load_policy(policy_path)
    failures: list[Finding] = []
    risks: list[Finding] = []

    try:
        xml_tree = ET.parse(path)
    except ET.ParseError as exc:
        return {
            "status": "failed",
            "population_count": 0,
            "inspected_count": 0,
            "failures": [asdict(Finding("malformed_xml", "error", "", "", str(exc)))],
            "semantic_review_risks": [],
            "shacl_conforms": False,
        }

    raw_annotations = [
        element for element in xml_tree.getroot().iter() if element.tag in TARGET_XML_NAMES
    ]
    for element in raw_annotations:
        language = element.attrib.get(XML_LANG)
        if language and not _valid_language_tag(language):
            failures.append(
                Finding(
                    "invalid_language_tag",
                    "error",
                    "",
                    element.tag,
                    f"Invalid BCP 47 language tag: {language}",
                )
            )

    try:
        graph = Graph().parse(path, format="xml")
    except Exception as exc:
        return {
            "status": "failed",
            "population_count": len(raw_annotations),
            "inspected_count": len(raw_annotations),
            "failures": [
                *[asdict(item) for item in failures],
                asdict(Finding("invalid_rdf", "error", "", "", str(exc))),
            ],
            "semantic_review_risks": [],
            "shacl_conforms": False,
        }

    annotations = sorted(
        ((s, p, o) for s, p, o in graph if p in TARGET_PREDICATES),
        key=lambda triple: tuple(map(str, triple)),
    )
    identities: Counter[tuple] = Counter()
    by_subject_language: dict[tuple[str, str], list[tuple[URIRef, str]]] = defaultdict(list)
    allowed_resource = {URIRef(value) for value in policy.get("resource_valued_predicates", [])}
    supported_languages = {
        str(value).lower() for value in policy.get("supported_languages", [])
    }
    sentinel_values = {str(value).strip().casefold() for value in policy.get("sentinel_values", ["null"])}

    for subject, predicate, obj in annotations:
        subject_text, predicate_text = str(subject), str(predicate)
        if not isinstance(subject, URIRef):
            failures.append(Finding("missing_subject_iri", "error", subject_text, predicate_text, "Annotation subject must be an IRI."))
        if not isinstance(obj, Literal):
            if predicate not in allowed_resource:
                failures.append(Finding("unsupported_object_kind", "error", subject_text, predicate_text, "Annotation value must be a literal."))
            continue
        value = str(obj)
        lang = obj.language.lower() if obj.language else None
        datatype = str(obj.datatype) if obj.datatype else None
        identities[(subject_text, predicate_text, lang, datatype, value)] += 1
        if not value.strip():
            failures.append(Finding("empty_annotation", "error", subject_text, predicate_text, "Annotation is empty or whitespace-only."))
        elif value.strip().casefold() in sentinel_values:
            failures.append(Finding("sentinel_annotation", "error", subject_text, predicate_text, "Annotation contains a configured sentinel value."))
        elif _looks_serialized_container(value):
            failures.append(Finding("serialized_container", "error", subject_text, predicate_text, "Annotation contains a serialized container."))
        if lang and not _valid_language_tag(lang):
            failures.append(Finding("invalid_language_tag", "error", subject_text, predicate_text, f"Invalid BCP 47 language tag: {lang}"))
        if lang and datatype and datatype != str(RDF.langString):
            failures.append(Finding("language_datatype_conflict", "error", subject_text, predicate_text, "Language-tagged literal has an incompatible datatype."))
        if lang:
            by_subject_language[(subject_text, lang.split("-")[0])].append((predicate, value))
            if _script_risk(value, lang):
                risks.append(Finding("script_mismatch", "review", subject_text, predicate_text, f"Text script is unusual for language {lang}."))
            if supported_languages and lang not in supported_languages:
                risks.append(Finding("unusual_language_tag", "review", subject_text, predicate_text, f"Regional language tag {lang} requires semantic review."))

    for identity, count in identities.items():
        if count > 1:
            failures.append(Finding("duplicate_logical_identity", "error", identity[0], identity[1], "Duplicate logical annotation identity."))

    for (subject, language), values in by_subject_language.items():
        base_labels = {text.casefold() for predicate, text in values if predicate in {RDFS.label, SKOS.prefLabel}}
        alt_labels = {text.casefold() for predicate, text in values if predicate == SKOS.altLabel}
        for duplicate in sorted(base_labels & alt_labels):
            risks.append(Finding("base_label_duplicate", "review", subject, str(SKOS.altLabel), f"Alternate label duplicates a base label: {duplicate}"))

    cardinality = policy.get("cardinality", {})
    counts = Counter((str(s), str(p)) for s, p, _ in annotations)
    subjects = {str(s) for s, _, _ in annotations}
    for predicate_text, bounds in cardinality.items():
        for subject in subjects:
            count = counts[(subject, predicate_text)]
            if "max" in bounds and count > int(bounds["max"]):
                failures.append(Finding("cardinality_violation", "error", subject, predicate_text, f"Cardinality {count} exceeds maximum {bounds['max']}."))

    conforms, _, report_text = shacl_validate(
        graph,
        shacl_graph=Graph().parse(shapes_path, format="turtle"),
        inference="none",
        abort_on_first=False,
    )
    if not conforms:
        failures.append(Finding("shacl_violation", "error", "", "", str(report_text)))
    return {
        "status": "failed" if failures else "complete",
        "population_count": len(annotations),
        "inspected_count": len(annotations),
        "failures": [asdict(item) for item in failures],
        "semantic_review_risks": [asdict(item) for item in risks],
        "shacl_conforms": bool(conforms),
    }


def compare_validation_results(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Classify candidate findings without forgiving newly introduced debt."""
    known = {canonical_finding(item) for item in baseline.get("failures", [])}
    candidate_failures = candidate.get("failures", [])
    regressions = [
        item for item in candidate_failures if canonical_finding(item) not in known
    ]
    return {
        **candidate,
        "status": "failed" if regressions else "complete",
        "failures": regressions,
        "all_candidate_failures": candidate_failures,
        "legacy_failure_count": len(candidate_failures) - len(regressions),
        "baseline_failure_count": len(baseline.get("failures", [])),
    }


def canonical_finding(finding: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return tuple(
        str(finding.get(field, ""))
        for field in ("code", "severity", "subject", "predicate", "message")
    )
