from __future__ import annotations

import sys
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import run_trusted_ontology_qa as runner
from ontology_qa.providers.base import ProviderReceipt
from ontology_qa.evals import load_cases, load_model_policy, load_slice_controls
from ontology_qa.corrections import make_correction
from ontology_qa.records import content_hash
from ontology_qa.replay import replay_bundle


def test_failed_validation_publishes_no_correction_artifacts(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate.owl"
    candidate.write_text("<candidate/>", encoding="utf-8")
    output = tmp_path / "generated"
    corrected = output / "corrected.owl"
    ledger = output / "ledger.json"
    evidence = output / "evidence.json"
    record_id = "a" * 64
    record = {
        "record_id": record_id,
        "subject": "https://example.test/subject",
        "predicate": "http://www.w3.org/2004/02/skos/core#definition",
        "family": "definition",
        "after": {"lexical": "bad", "language": "en", "datatype": None},
    }
    review = {
        "payload": {
            "responses": [{
                "record_id": record_id,
                "verdict": "defect",
                "confidence": 1.0,
                "defect_types": ["incorrect_meaning"],
                "rationale": "incorrect",
            }]
        }
    }
    qualification = {
        "route_id": "provider:model",
        "qualification_hash": "q" * 64,
    }
    qualifications = {
        role: qualification
        for role in (
            "production-primary",
            "production-independent",
            "correction-proposer",
            "correction-verifier-1",
            "correction-verifier-2",
        )
    }
    correction = {
        "root_record_id": record_id,
        "revision_id": "b" * 64,
        "replacement": "good",
    }

    monkeypatch.setattr(
        runner,
        "converge_correction",
        lambda *args, **kwargs: {"state": "verified", "correction": correction},
    )
    monkeypatch.setattr(
        runner, "correction_response_schema", lambda *args, **kwargs: {}
    )

    def apply(_source, output, _corrections):
        Path(output).write_text("<corrected/>", encoding="utf-8")
        return {"output_hash": "c" * 64}

    monkeypatch.setattr(runner, "apply_correction_batch", apply)
    monkeypatch.setattr(runner, "validate_ontology", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        runner,
        "compare_validation_results",
        lambda *args, **kwargs: {"failures": ["introduced defect"]},
    )

    with pytest.raises(ValueError, match="introduced deterministic failures"):
        runner._run_changed_record_corrections(
            records=[record],
            primary=review,
            independent=review,
            candidate=candidate,
            corrected_output=corrected,
            ledger_output=ledger,
            evidence_output=evidence,
            adapters={},
            qualifications=qualifications,
            executor=SimpleNamespace(),
            schema={},
            model_policy={"minimum_confidence": 0.9},
            policy_hash="p" * 64,
            batch_size=1,
        )

    assert not corrected.exists()
    assert not ledger.exists()
    assert not evidence.exists()


def test_verified_correction_publishes_complete_batch(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate.owl"
    output = tmp_path / "generated"
    corrected = output / "corrected.owl"
    ledger = output / "ledger.json"
    evidence = output / "evidence.json"
    subject = "https://example.test/Thing"
    predicate = "http://www.w3.org/2004/02/skos/core#definition"
    candidate.write_text(f"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:owl="http://www.w3.org/2002/07/owl#"
 xmlns:skos="http://www.w3.org/2004/02/skos/core#">
 <owl:Class rdf:about="{subject}">
  <skos:definition xml:lang="en">Bad definition.</skos:definition>
 </owl:Class>
</rdf:RDF>
""")
    record_id = "a" * 64
    record = {
        "record_id": record_id,
        "subject": subject,
        "predicate": predicate,
        "family": "definition",
        "after": {
            "subject": subject,
            "predicate": predicate,
            "object_kind": "literal",
            "language": "en",
            "datatype": None,
            "lexical": "Bad definition.",
        },
    }
    response = {
        "record_id": record_id,
        "verdict": "defect",
        "confidence": 1.0,
        "defect_types": ["other"],
        "rationale": "The definition is wrong.",
    }
    reviews = {"payload": {"responses": [response]}}
    roles = (
        "production-primary",
        "production-independent",
        "correction-proposer",
        "correction-verifier-1",
        "correction-verifier-2",
    )
    qualifications = {
        role: {
            "route_id": f"provider:{role}",
            "qualification_hash": content_hash(role),
        }
        for role in roles
    }
    correction = make_correction(
        root_record_id=record_id,
        subject=subject,
        predicate=predicate,
        language="en",
        datatype=None,
        before="Bad definition.",
        replacement="Accurate definition.",
        proposer_route=qualifications["correction-proposer"]["route_id"],
        verifier_routes=[
            qualifications["correction-verifier-1"]["route_id"],
            qualifications["correction-verifier-2"]["route_id"],
        ],
        verifier_qualification_hashes=[
            qualifications["correction-verifier-1"]["qualification_hash"],
            qualifications["correction-verifier-2"]["qualification_hash"],
        ],
    )
    monkeypatch.setattr(
        runner,
        "converge_correction",
        lambda *args, **kwargs: {"state": "verified", "correction": correction},
    )
    monkeypatch.setattr(runner, "validate_ontology", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        runner,
        "compare_validation_results",
        lambda *args, **kwargs: {"failures": []},
    )
    monkeypatch.setattr(
        runner,
        "_call",
        lambda adapter, records, schema, **kwargs: [{
            "record_id": item["record_id"],
            "verdict": "pass",
            "confidence": 1.0,
        } for item in records],
    )
    executor = SimpleNamespace(
        budget=SimpleNamespace(snapshot=lambda: {}), cache_hits=0
    )
    schema = json.loads(
        (runner.ROOT / "schemas/ontology-review.schema.json").read_text()
    )

    result = runner._run_changed_record_corrections(
        records=[record],
        primary=reviews,
        independent=reviews,
        candidate=candidate,
        corrected_output=corrected,
        ledger_output=ledger,
        evidence_output=evidence,
        adapters={role: object() for role in roles},
        qualifications=qualifications,
        executor=executor,
        schema=schema,
        model_policy={"minimum_confidence": 0.9},
        policy_hash="p" * 64,
        batch_size=1,
    )

    assert result["status"] == "correction_ready"
    assert "Accurate definition." in corrected.read_text()
    assert json.loads(ledger.read_text()) == [correction]
    assert json.loads(evidence.read_text())["candidate_hash"] == result["candidate_hash"]


def test_trusted_runner_accepts_with_stubbed_independent_providers(
    tmp_path, monkeypatch, capsys
):
    baseline = tmp_path / "baseline.owl"
    candidate = tmp_path / "candidate.owl"
    template = """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:owl="http://www.w3.org/2002/07/owl#"
 xmlns:skos="http://www.w3.org/2004/02/skos/core#">
 <owl:Class rdf:about="https://example.test/Thing">
  <skos:prefLabel xml:lang="en">Thing</skos:prefLabel>
  <skos:definition xml:lang="en">{definition}</skos:definition>
 </owl:Class>
</rdf:RDF>
"""
    baseline.write_text(template.format(definition="Old definition."))
    candidate.write_text(template.format(definition="Clear new definition."))
    policy = load_model_policy(runner.ROOT / "qa/ontology/model-policy.yaml")
    required_slices = {
        (family, locale)
        for family, locales in policy["required_slices"].items()
        for locale in locales
    }
    cases = [
        case
        for path in (
            runner.ROOT / "qa/ontology/evals/cases.jsonl",
            runner.ROOT / "qa/ontology/evals/held-out.jsonl",
        )
        for case in load_cases(path)
    ]
    controls = load_slice_controls(
        runner.ROOT / "qa/ontology/evals/slice-controls.json",
        required_slices,
    )
    verdicts = {
        content_hash(case["case_id"]): (
            case["expected_verdict"] or "pass",
            case["expected_defect_types"],
            None,
        )
        for case in [*cases, *controls]
    }
    for case in controls:
        if case["expected_verdict"] != "defect":
            continue
        replacement = case["input"]["source"]
        verdicts[content_hash(case["case_id"])] = (
            "defect", case["expected_defect_types"], replacement
        )
        verdicts[content_hash(case["case_id"] + "-repaired")] = (
            "pass", [], None
        )
        verdicts[content_hash(case["case_id"] + "-unrepaired")] = (
            "defect", case["expected_defect_types"], None
        )

    class StubAdapter:
        def __init__(self, provider, model):
            self.provider = provider
            self.model = model
            self.reasoning = "high"
            self.max_output_tokens = 1

        def assess(self, request):
            responses = []
            proposer = request.schema["properties"]["proposed_replacement"].get(
                "type"
            ) == "string"
            for record in request.records:
                verdict, defects, replacement = verdicts.get(
                    record["record_id"], ("pass", [], None)
                )
                if proposer:
                    verdict = "defect"
                    replacement = record["expected_replacement"]
                responses.append({
                    "record_id": record["record_id"],
                    "verdict": verdict,
                    "confidence": 1.0,
                    "defect_types": defects,
                    "evidence_spans": [{
                        "source": "context", "quote": record["record_id"]
                    }],
                    "preserved_propositions": ["Meaning is preserved."],
                    "rationale": "The expected controlled verdict applies.",
                    "proposed_replacement": replacement if proposer else None,
                })
            return ProviderReceipt(
                provider=self.provider,
                requested_model=self.model,
                actual_model=self.model,
                request_id=request.request_id,
                responses=tuple(responses),
            )

    monkeypatch.setattr(
        runner,
        "_adapter",
        lambda route, maximum_output_tokens: StubAdapter(
            route["provider"], route["model"]
        ),
    )

    bundle = tmp_path / "bundle"
    monkeypatch.setattr(sys, "argv", [
        "run_trusted_ontology_qa.py",
        "--baseline", str(baseline),
        "--candidate", str(candidate),
        "--reviewed-sha", "1" * 40,
        "--bundle", str(bundle),
        "--cache", str(tmp_path / "cache"),
        "--corrected-output", str(tmp_path / "unused" / "corrected.owl"),
        "--generated-correction-ledger", str(tmp_path / "unused" / "ledger.json"),
        "--generated-correction-evidence", str(tmp_path / "unused" / "evidence.json"),
    ])

    assert runner.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["release_decision"] == "merge_gate_passed"
    report = json.loads((bundle / "report.json").read_text())
    assert report["payload"]["release_decision"] == "merge_gate_passed"
    assert (bundle / "index.json").is_file()
    replayed = replay_bundle(
        bundle,
        report_schema_path=runner.ROOT / "schemas/ontology-qa-report.schema.json",
    )
    assert replayed["verified"] is True
    for name in (
        "model-policy.yaml",
        "review-policy.yaml",
        "review-schema.json",
        "eval-cases.jsonl",
        "prompt-definition.md",
        "tool-manifest.json",
        "primary_qualification.json",
        "surveillance.json",
        "candidate.owl",
    ):
        path = bundle / name
        original = path.read_bytes()
        if name == "review-schema.json":
            tampered = original.replace(
                b'"title": "', b'"title": "tampered ', 1
            )
        elif name == "eval-cases.jsonl":
            tampered = original.replace(
                b'"case_id":"', b'"case_id":"tampered-', 1
            )
        else:
            tampered = original + b" "
        path.write_bytes(tampered)
        try:
            replay_bundle(
                bundle,
                report_schema_path=(
                    runner.ROOT / "schemas/ontology-qa-report.schema.json"
                ),
            )
        except ValueError:
            pass
        else:
            pytest.fail(f"tampered production binding was accepted: {name}")
        path.write_bytes(original)
