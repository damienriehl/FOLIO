"""Bounded, content-addressed ontology review context."""

from __future__ import annotations

from typing import Any

from .records import canonical_json, content_hash


def build_context(
    record: dict[str, Any],
    *,
    concept_label: str,
    ancestors: list[str],
    siblings: list[str],
    risk_evidence: list[dict[str, Any]],
    maximum_items: int = 12,
    maximum_chars: int = 8000,
) -> dict[str, Any]:
    context = {
        "record": record,
        "concept_label": concept_label,
        "ancestors": sorted(set(ancestors))[:maximum_items],
        "siblings": sorted(set(siblings))[:maximum_items],
        "risk_evidence": risk_evidence[:maximum_items],
    }
    encoded = canonical_json(context)
    if len(encoded) > maximum_chars:
        context["ancestors"] = context["ancestors"][:3]
        context["siblings"] = context["siblings"][:3]
        context["risk_evidence"] = context["risk_evidence"][:3]
        encoded = canonical_json(context)
    if len(encoded) > maximum_chars:
        raise ValueError("review context exceeds configured bound")
    return {"context_hash": content_hash(encoded), **context}
