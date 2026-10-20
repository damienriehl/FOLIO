"""Serialization-insensitive semantic hydration delta generation."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable

from rdflib import Graph, Literal, URIRef
from rdflib.compare import graph_diff, isomorphic, to_canonical_graph

from .records import (
    AnnotationValue,
    DeltaRecord,
    artifact_envelope,
    canonical_json,
    content_hash,
)


def _annotation_values(graph: Graph) -> set[AnnotationValue]:
    values: set[AnnotationValue] = set()
    for subject, predicate, obj in graph:
        if not isinstance(subject, URIRef) or not isinstance(predicate, URIRef):
            continue
        if isinstance(obj, Literal):
            values.add(
                AnnotationValue(
                    subject=str(subject),
                    predicate=str(predicate),
                    lexical=str(obj),
                    language=obj.language,
                    datatype=str(obj.datatype) if obj.datatype else None,
                )
            )
    return values


def _single_pairs(
    removed: set[AnnotationValue], added: set[AnnotationValue]
) -> tuple[list[DeltaRecord], set[AnnotationValue], set[AnnotationValue]]:
    records: list[DeltaRecord] = []
    remaining_removed = set(removed)
    remaining_added = set(added)

    # Retags preserve lexical content while changing language/datatype metadata.
    old_by_lexical: dict[tuple[str, str, str], list[AnnotationValue]] = defaultdict(list)
    new_by_lexical: dict[tuple[str, str, str], list[AnnotationValue]] = defaultdict(list)
    for item in removed:
        old_by_lexical[(item.subject, item.predicate, item.lexical)].append(item)
    for item in added:
        new_by_lexical[(item.subject, item.predicate, item.lexical)].append(item)
    for key in sorted(old_by_lexical):
        olds, news = old_by_lexical[key], new_by_lexical.get(key, [])
        if len(olds) == len(news) == 1:
            old, new = olds[0], news[0]
            records.append(DeltaRecord("retagged", new.locator, old, new))
            remaining_removed.remove(old)
            remaining_added.remove(new)

    # Only pair an unambiguous one-to-one lexical replacement.
    old_by_locator: dict[tuple, list[AnnotationValue]] = defaultdict(list)
    new_by_locator: dict[tuple, list[AnnotationValue]] = defaultdict(list)
    locator_key = lambda item: tuple(sorted(item.locator.items()))
    for item in remaining_removed:
        old_by_locator[locator_key(item)].append(item)
    for item in remaining_added:
        new_by_locator[locator_key(item)].append(item)
    for key in sorted(old_by_locator):
        olds, news = old_by_locator[key], new_by_locator.get(key, [])
        if len(olds) == len(news) == 1:
            old, new = olds[0], news[0]
            records.append(DeltaRecord("replaced", new.locator, old, new))
            remaining_removed.remove(old)
            remaining_added.remove(new)
    return records, remaining_removed, remaining_added


def build_hydration_manifest(
    baseline_path: str | Path,
    candidate_path: str | Path,
    *,
    run_id: str,
    attempt_id: str,
    baseline_sha: str | None = None,
    candidate_sha: str | None = None,
    parent_hashes: Iterable[str] = (),
    policy_hash: str = "unconfigured",
    tool_hash: str = "unconfigured",
) -> dict:
    baseline_bytes = Path(baseline_path).read_bytes()
    candidate_bytes = Path(candidate_path).read_bytes()
    baseline_hash = content_hash(baseline_bytes)
    candidate_hash = content_hash(candidate_bytes)
    if baseline_sha and baseline_sha != baseline_hash:
        raise ValueError("baseline hash does not match immutable input")
    if candidate_sha and candidate_sha != candidate_hash:
        raise ValueError("candidate hash does not match immutable input")

    if baseline_hash == candidate_hash:
        records: list[DeltaRecord] = []
        baseline = candidate = Graph()
    else:
        baseline = Graph().parse(data=baseline_bytes, format="xml")
        candidate = Graph().parse(data=candidate_bytes, format="xml")
    if baseline_hash != candidate_hash and isomorphic(baseline, candidate):
        records = []
    elif baseline_hash != candidate_hash:
        old_values = _annotation_values(baseline)
        new_values = _annotation_values(candidate)
        removed, added = old_values - new_values, new_values - old_values
        records, removed, added = _single_pairs(removed, added)
        records.extend(DeltaRecord("removed", item.locator, item, None) for item in removed)
        records.extend(DeltaRecord("added", item.locator, None, item) for item in added)

    canonical_records = sorted(
        (record.canonical() for record in records), key=lambda item: item["record_id"]
    )
    _, baseline_only, candidate_only = graph_diff(
        to_canonical_graph(baseline), to_canonical_graph(candidate)
    )
    semantic_drift = sorted(
        {
            (side, str(s), str(p), str(o))
            for side, graph in (("removed", baseline_only), ("added", candidate_only))
            for s, p, o in graph
            if not (isinstance(s, URIRef) and isinstance(p, URIRef) and isinstance(o, Literal))
        }
    )
    payload = {
        "records": canonical_records,
        "record_count": len(canonical_records),
        "unrelated_semantic_drift": [list(item) for item in semantic_drift],
    }
    return artifact_envelope(
        payload=payload,
        run_id=run_id,
        attempt_id=attempt_id,
        parent_hashes=list(parent_hashes),
        baseline_hash=baseline_hash,
        candidate_hash=candidate_hash,
        policy_hash=policy_hash,
        tool_hash=tool_hash,
        status="complete",
    )


def manifest_bytes(manifest: dict) -> bytes:
    return canonical_json(manifest) + b"\n"
