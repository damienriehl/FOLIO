from __future__ import annotations

import json
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from ontology_qa.model_review import run_blind_review
from ontology_qa.context import build_graph_context
from ontology_qa.providers.google import GoogleAdapter, _gemini_transport
from ontology_qa.providers.openai import OpenAIAdapter
from ontology_qa.providers.base import ProviderError, ReviewRequest
from ontology_qa.records import canonical_json
from run_trusted_ontology_qa import _provider_schema

ROOT = Path(__file__).parents[1]
SCHEMA = json.loads((ROOT / "schemas/ontology-review.schema.json").read_text())
RID = "a" * 64


def response(record_id=RID, verdict="pass", confidence=0.99):
    return {
        "record_id": record_id, "verdict": verdict, "confidence": confidence,
        "defect_types": [], "evidence_spans": [
            {"source": "annotation", "quote": RID},
        ],
        "preserved_propositions": ["meaning preserved"], "rationale": "supported",
        "proposed_replacement": None,
    }


def invoke(adapter, records=None, candidate_hash="candidate"):
    return run_blind_review(
        adapter, records=records or [{"record_id": RID}], prompt="rubric", schema=SCHEMA,
        context_hash="context", qualification_hash="q" * 64, run_id="run",
        attempt_id="attempt", baseline_hash="baseline", candidate_hash=candidate_hash,
        policy_hash="policy", tool_hash="tool",
    )


def test_provider_adapters_receive_identical_blind_inputs():
    seen = []
    def transport(payload):
        seen.append(payload)
        return {"model": payload["model"], "responses": [response()]}
    left = invoke(OpenAIAdapter("gpt-5.6-sol", transport))
    right = invoke(GoogleAdapter("gemini-3.5-flash", transport))
    assert left["status"] == right["status"] == "complete"
    assert seen[0]["input"] == seen[1]["contents"]
    assert "responses" not in seen[0]["input"][0]


def test_gemini_25_uses_dynamic_thinking_budget():
    seen = []
    adapter = GoogleAdapter(
        "gemini-2.5-pro",
        lambda payload: (
            seen.append(payload)
            or {"model": payload["model"], "responses": [response()]}
        ),
    )
    invoke(adapter)
    assert seen[0]["generation_config"]["thinking_config"] == {
        "thinking_budget": -1
    }


def test_omitted_or_invented_ids_fail_completeness():
    adapter = OpenAIAdapter("gpt-5.6-sol", lambda payload: {
        "model": payload["model"], "responses": [response("b" * 64)]
    })
    assert invoke(adapter)["status"] == "incomplete"


def test_unpinned_model_fails_without_substitution():
    adapter = OpenAIAdapter("gpt-5.6-sol", lambda payload: {
        "model": "alias-latest", "responses": [response()]
    })
    result = invoke(adapter)
    assert result["status"] == "incomplete"
    assert "unpinned" in result["payload"]["error"]


def test_transient_failure_retries_same_immutable_request(monkeypatch):
    calls = []
    delays = []
    monkeypatch.setattr(
        "ontology_qa.providers.base.time.sleep", delays.append
    )
    def transport(payload):
        calls.append(payload)
        if len(calls) == 1:
            raise ProviderError("rate limited", transient=True)
        return {"model": payload["model"], "responses": [response()]}
    result = invoke(OpenAIAdapter("gpt-5.6-sol", transport))
    assert result["status"] == "complete"
    assert result["payload"]["retry_count"] == 1
    assert calls[0] == calls[1]
    assert len(delays) == 1
    assert delays[0] >= 1


@pytest.mark.parametrize(
    ("adapter", "variable"),
    [
        (OpenAIAdapter("gpt-5.6-sol"), "OPENAI_API_KEY"),
        (GoogleAdapter("gemini-3.5-flash"), "GOOGLE_API_KEY"),
    ],
)
def test_default_live_transport_fails_closed_without_credentials(
    monkeypatch, adapter, variable
):
    monkeypatch.delenv(variable, raising=False)
    request = ReviewRequest(
        request_id="request", model=adapter.model, prompt="review",
        records=(), schema={"type": "object"}, context_hash="context",
    )
    with pytest.raises(ProviderError, match=variable):
        adapter.assess(request)


def test_google_api_key_is_sent_in_header_not_url(monkeypatch):
    seen = []

    def urlopen(request, timeout):
        seen.append(request)
        return io.BytesIO(json.dumps({
            "modelVersion": "gemini-3.5-flash",
            "candidates": [{
                "content": {"parts": [{"text": "[]"}]},
            }],
        }).encode())

    monkeypatch.setenv("GOOGLE_API_KEY", "secret-key")
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    _gemini_transport({
        "model": "gemini-3.5-flash",
        "system_instruction": "review",
        "contents": [],
        "generation_config": {
            "response_mime_type": "application/json",
            "response_json_schema": {"type": "array"},
            "thinking_config": {"thinking_level": "high"},
            "max_output_tokens": 100,
        },
    })
    assert "secret-key" not in seen[0].full_url
    assert seen[0].get_header("X-goog-api-key") == "secret-key"


def test_graph_context_is_bounded_hashed_and_ontology_grounded():
    from rdflib import Graph, Literal, URIRef
    from rdflib.namespace import RDFS, SKOS

    graph = Graph()
    concept = URIRef("https://example.test/C")
    parent = URIRef("https://example.test/P")
    sibling = URIRef("https://example.test/S")
    graph.add((concept, SKOS.prefLabel, Literal("Appeal", lang="en")))
    graph.add((
        concept, SKOS.definition,
        Literal("A review by a higher court.", lang="en"),
    ))
    graph.add((concept, RDFS.subClassOf, parent))
    graph.add((parent, SKOS.prefLabel, Literal("Procedure", lang="en")))
    graph.add((sibling, RDFS.subClassOf, parent))
    graph.add((sibling, SKOS.prefLabel, Literal("Review", lang="en")))
    record = {
        "record_id": RID,
        "after": {
            "subject": str(concept), "predicate": str(SKOS.definition),
            "lexical": "A review by a higher court.", "language": "en",
            "datatype": None, "object_kind": "literal",
        },
    }
    first = build_graph_context(graph, record, risk_evidence=[])
    second = build_graph_context(graph, record, risk_evidence=[])
    assert first == second
    record["context"] = first
    assert json.loads(canonical_json(record))["context"]["concept_label"] == "Appeal"
    assert first["concept_label"] == "Appeal"
    assert first["concept_definition"] == {
        "predicate": str(SKOS.definition),
        "language": "en",
        "lexical": "A review by a higher court.",
    }
    assert first["ancestors"] == ["Procedure"]
    assert first["siblings"] == ["Review"]
    assert len(first["context_hash"]) == 64


def test_provider_schema_removes_unsupported_composition_only():
    schema = {
        "type": "object",
        "properties": {"verdict": {"type": "string"}},
        "required": ["verdict"],
        "additionalProperties": False,
        "allOf": [{"if": {}, "then": {}}],
    }
    projected = _provider_schema(schema)
    assert "allOf" not in projected
    assert projected["required"] == ["verdict"]
    assert projected["additionalProperties"] is False
