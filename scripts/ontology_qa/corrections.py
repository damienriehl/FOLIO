"""Copy-on-write verified ontology correction transactions."""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from rdflib import BNode, Graph, Literal, URIRef

from .records import AnnotationValue, canonical_json, content_hash


def make_correction(
    *,
    root_record_id: str,
    subject: str,
    predicate: str,
    language: str | None,
    datatype: str | None,
    before: str,
    replacement: str,
    proposer_route: str,
    verifier_routes: list[str],
    verifier_qualification_hashes: list[str],
) -> dict[str, Any]:
    if len(set(verifier_routes)) != 2 or proposer_route in verifier_routes:
        raise ValueError("correction requires two distinct verifier routes excluding proposer")
    if len(set(verifier_qualification_hashes)) != 2:
        raise ValueError("correction requires two distinct verifier qualifications")
    old = AnnotationValue(subject, predicate, before, language=language, datatype=datatype)
    new = AnnotationValue(subject, predicate, replacement, language=language, datatype=datatype)
    lineage = {
        "root_record_id": root_record_id,
        "before_hash": old.value_hash,
        "replacement_hash": new.value_hash,
    }
    return {
        **lineage,
        "revision_id": content_hash(canonical_json(lineage)),
        "subject": subject, "predicate": predicate, "language": language,
        "datatype": datatype, "before": before, "replacement": replacement,
        "proposer_route": proposer_route, "verifier_routes": verifier_routes,
        "verifier_qualification_hashes": verifier_qualification_hashes,
    }


def _prefix_for_predicate(xml_bytes: bytes, predicate: str) -> str:
    namespaces = dict(
        (prefix or "", uri)
        for _, (prefix, uri) in ET.iterparse(
            io.BytesIO(xml_bytes), events=("start-ns",)
        )
    )
    matches = [(prefix, uri) for prefix, uri in namespaces.items() if predicate.startswith(uri)]
    if not matches:
        raise ValueError(f"predicate namespace is not declared: {predicate}")
    prefix, uri = max(matches, key=lambda item: len(item[1]))
    local = predicate[len(uri):]
    return f"{prefix}:{local}" if prefix else local


def _replace_once(xml_text: str, xml_bytes: bytes, correction: dict[str, Any]) -> str:
    subject = re.escape(correction["subject"])
    block_pattern = re.compile(
        rf'(<(?P<node_tag>[\w:.-]+)\b[^>]*\brdf:about="{subject}"[^>]*>)(.*?)(</(?P=node_tag)>)',
        re.DOTALL,
    )
    blocks = list(block_pattern.finditer(xml_text))
    if len(blocks) != 1:
        raise ValueError("correction subject must match exactly one RDF/XML block")
    tag = re.escape(_prefix_for_predicate(xml_bytes, correction["predicate"]))
    entities = {'"': "&quot;", "'": "&apos;"}
    old = re.escape(escape(correction["before"], entities))
    value_pattern = re.compile(
        rf'(<{tag}\b(?P<attrs>[^>]*)>){old}(</{tag}>)', re.DOTALL
    )
    block = blocks[0].group(0)
    matches = list(value_pattern.finditer(block))
    filtered = []
    for match in matches:
        attrs = match.group("attrs")
        language = correction["language"]
        datatype = correction["datatype"]
        if language and not re.search(rf'\bxml:lang="{re.escape(language)}"', attrs, re.I):
            continue
        if datatype and not re.search(rf'\brdf:datatype="{re.escape(datatype)}"', attrs):
            continue
        filtered.append(match)
    if len(filtered) != 1:
        raise ValueError("correction locator must match exactly one annotation")
    match = filtered[0]
    replacement = escape(correction["replacement"], entities)
    new_block = block[:match.start()] + match.group(1) + replacement + match.group(3) + block[match.end():]
    return xml_text[:blocks[0].start()] + new_block + xml_text[blocks[0].end():]


def apply_correction_batch(
    source_path: str | Path,
    output_path: str | Path,
    corrections: list[dict[str, Any]],
) -> dict[str, Any]:
    source = Path(source_path)
    original_bytes = source.read_bytes()
    original_text = original_bytes.decode("utf-8")
    before_graph = Graph().parse(data=original_bytes, format="xml")
    working = original_text
    removed, added = set(), set()
    seen_revisions = set()
    lineage_values: dict[tuple[str, str, str | None, str | None], set[str]] = {}
    for correction in corrections:
        if correction["revision_id"] in seen_revisions:
            raise ValueError("repeated correction revision")
        seen_revisions.add(correction["revision_id"])
        old = AnnotationValue(
            correction["subject"], correction["predicate"], correction["before"],
            language=correction["language"], datatype=correction["datatype"],
        )
        new = AnnotationValue(
            correction["subject"], correction["predicate"], correction["replacement"],
            language=correction["language"], datatype=correction["datatype"],
        )
        if old.value_hash != correction["before_hash"] or new.value_hash != correction["replacement_hash"]:
            raise ValueError("correction value hash mismatch")
        locator = (old.subject, old.predicate, old.language, old.datatype)
        seen_values = lineage_values.setdefault(locator, {old.value_hash})
        if new.value_hash in seen_values:
            raise ValueError("correction lineage repeats a prior candidate")
        seen_values.add(new.value_hash)
        try:
            working = _replace_once(working, original_bytes, correction)
        except ValueError as exc:
            raise ValueError(
                f"correction {correction['root_record_id']} failed: {exc}"
            ) from exc
        removed.add((URIRef(old.subject), URIRef(old.predicate), Literal(old.lexical, lang=old.language, datatype=URIRef(old.datatype) if old.datatype else None)))
        added.add((URIRef(new.subject), URIRef(new.predicate), Literal(new.lexical, lang=new.language, datatype=URIRef(new.datatype) if new.datatype else None)))
    candidate_bytes = working.encode("utf-8")
    after_graph = Graph().parse(data=candidate_bytes, format="xml")
    if len(before_graph) != len(after_graph):
        raise ValueError("corrected graph changed the triple count")
    if any(triple in after_graph for triple in removed):
        raise ValueError("corrected graph retains a replaced annotation")
    if any(triple not in after_graph for triple in added):
        raise ValueError("corrected graph omits an authorized replacement")
    stable_before = {
        triple for triple in before_graph
        if triple not in removed
        and not any(isinstance(node, BNode) for node in triple)
    }
    stable_after = {
        triple for triple in after_graph
        if triple not in added
        and not any(isinstance(node, BNode) for node in triple)
    }
    if stable_before != stable_after:
        raise ValueError("corrected graph contains changes outside the authorized ledger")
    destination = Path(output_path)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(candidate_bytes)
    temporary.replace(destination)
    return {
        "source_hash": content_hash(original_bytes),
        "output_hash": content_hash(candidate_bytes),
        "correction_count": len(corrections),
        "revision_ids": [item["revision_id"] for item in corrections],
    }
