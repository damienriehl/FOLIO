#!/usr/bin/env python3
"""Create the predicate that GitHub OIDC signs for an accepted ontology."""

import argparse
import json
from pathlib import Path

from ontology_qa.attestation import build_acceptance_predicate
from ontology_qa.records import canonical_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--candidate-repository")
    parser.add_argument("--workflow-ref", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--tree-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--bundle-digest", required=True)
    parser.add_argument("--expires-at", required=True)
    args = parser.parse_args()
    predicate = build_acceptance_predicate(
        repository=args.repository, candidate_repository=args.candidate_repository,
        workflow_ref=args.workflow_ref,
        commit_sha=args.commit_sha, tree_sha=args.tree_sha,
        run_id=args.run_id, run_attempt=args.run_attempt,
        report=json.loads(Path(args.report).read_text()),
        evidence_bundle_digest=args.bundle_digest, expires_at=args.expires_at,
    )
    Path(args.output).write_bytes(canonical_json(predicate) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
