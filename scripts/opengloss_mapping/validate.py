"""Independently validate the embedded-YAML SSSOM mapping contract."""
from __future__ import annotations

import csv
from dataclasses import dataclass
import io
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import yaml

CURIE_MAP = {
    "FOLIO": "https://folio.openlegalstandard.org/",
    "OGS": "tag:folio.openlegalstandard.org,2026:opengloss/sense/",
    "OGL": "tag:folio.openlegalstandard.org,2026:opengloss/lexeme/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "semapv": "https://w3id.org/semapv/vocab/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "sssom": "https://w3id.org/sssom/",
}
COLUMNS = "subject_id subject_label predicate_id object_id object_label mapping_justification confidence subject_match_field object_match_field match_string comment".split()
REQUIRED_KEYS = "curie_map mapping_set_id mapping_set_version mapping_set_title mapping_set_description license mapping_date mapping_tool mapping_tool_version subject_source subject_source_version object_source object_source_version".split()
PREDICATES = {f"skos:{name}Match" for name in ("exact", "close", "broad", "narrow", "related")}
CURIE_FIELDS = "subject_id predicate_id object_id mapping_justification subject_match_field object_match_field".split()
FORBIDDEN = re.compile(r"owl:sameAs|owl:equivalentClass|owl#sameAs|owl#equivalentClass|openGlossID", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    row: int | None = None


class MappingRows(list):
    """Rows plus original syntax needed to check empty files and discarded text."""

    def __init__(self, rows: list[dict], columns: list[str], raw: str):
        super().__init__(rows)
        self.columns = columns
        self.raw = raw


def read_mapping_set(path: str | Path) -> tuple[dict, list[dict]]:
    """Read leading comment YAML and unquoted tab-separated records."""
    raw = Path(path).read_text(encoding="utf-8")
    lines = raw.splitlines(keepends=True)
    header_lines = []
    offset = 0
    for line in lines:
        if not line.startswith("#"):
            break
        content = line[1:]
        header_lines.append(content[1:] if content.startswith(" ") else content)
        offset += 1
    header = yaml.safe_load("".join(header_lines)) or {}
    if not isinstance(header, dict):
        raise ValueError("SSSOM YAML header must be a mapping")
    reader = csv.DictReader(io.StringIO("".join(lines[offset:])), delimiter="\t", quoting=csv.QUOTE_NONE)
    columns = reader.fieldnames or []
    return header, MappingRows(list(reader), columns, raw)


def _active_classes(path: str | Path) -> set[str]:
    owl = "{http://www.w3.org/2002/07/owl#}"
    about = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about"
    active, deprecated = set(), set()
    for _, element in ET.iterparse(path, events=("end",)):
        if element.tag == owl + "Class":
            iri = element.get(about)
            if iri:
                active.add(iri)
                if any((node.text or "").strip().lower() in {"true", "1"}
                       for node in element.findall(owl + "deprecated")):
                    deprecated.add(iri)
            element.clear()
    return active - deprecated


def validate(header: dict, rows: list[dict], folio_path: str | Path | None = None) -> list[Finding]:
    """Return all violations; row numbers count data records starting at one."""
    findings = []
    def add(code: str, message: str, row: int | None = None) -> None:
        findings.append(Finding(code, f"row {row}: {message}" if row else message, row))

    for key in REQUIRED_KEYS:
        value = header.get(key)
        if not value or (isinstance(value, str) and not value.strip()):
            add("header-missing-key", f"missing or empty header key: {key}")
    curies = header.get("curie_map")
    if not isinstance(curies, dict):
        curies = {}
    for prefix in ("FOLIO", "OGS", "OGL", "skos", "semapv"):
        if curies.get(prefix) != CURIE_MAP[prefix]:
            add("curie-map", f"incorrect or missing expansion for {prefix}")
    columns = getattr(rows, "columns", list(rows[0]) if rows else COLUMNS)
    if columns != COLUMNS:
        add("columns", "column header must equal: " + "\t".join(COLUMNS))
    # Inspect raw bytes as text too: YAML comments and extra TSV fields count.
    text = getattr(rows, "raw", "") + repr(header) + repr(list(rows))
    if FORBIDDEN.search(text):
        add("forbidden", "file contains a forbidden identifier")
    active = _active_classes(folio_path) if folio_path is not None else None
    previous = None
    seen = set()
    for number, row in enumerate(rows, 1):
        if list(row) != COLUMNS or any(value is None for value in row.values()):
            add("columns", "record does not have exactly the required columns", number)
        def value(key: str) -> str:
            item = row.get(key, "")
            return item if isinstance(item, str) else ""
        for field in CURIE_FIELDS:
            curie = value(field)
            prefix, separator, local = curie.partition(":")
            if not separator or not local or not isinstance(curies.get(prefix), str) or not curies[prefix].strip():
                add("curie-map", f"unmapped CURIE in {field}: {curie!r}", number)
        subject, predicate, obj = (value(k) for k in ("subject_id", "predicate_id", "object_id"))
        if predicate not in PREDICATES:
            add("predicate", f"unsupported predicate: {predicate!r}", number)
        if not re.fullmatch(r"OGS:[^\s|,;:]+:[a-z]+:\d+", obj):
            add("object-id", f"invalid single sense CURIE: {obj!r}", number)
        if not re.fullmatch(r"FOLIO:[A-Za-z0-9_-]+", subject):
            add("subject-id", f"invalid subject CURIE: {subject!r}", number)
        try:
            confidence = float(value("confidence"))
        except ValueError:
            confidence = float("nan")
        if not 0 < confidence <= 1:
            add("confidence", "confidence must be a number in (0, 1]", number)
        if not value("mapping_justification").startswith("semapv:"):
            add("justification", "mapping_justification must start with semapv:", number)
        key = (subject, predicate, obj)
        if previous is not None and key < previous:
            add("order", "rows must be sorted by subject, predicate, object", number)
        previous = key
        pair = (subject, obj)
        if pair in seen:
            add("duplicate", f"duplicate subject/object pair: {pair}", number)
        seen.add(pair)
        if active is not None:
            iri = str(curies.get("FOLIO", "")) + subject.removeprefix("FOLIO:")
            if iri not in active:
                add("folio-subject", f"subject is absent or deprecated: {subject}", number)
    return findings
