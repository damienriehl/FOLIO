#!/usr/bin/env python3
"""Offline-verify a signed acceptance predicate and its evidence bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ontology_qa.attestation import verify_acceptance_handoff


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predicate", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--bundle-archive", required=True)
    parser.add_argument("--report-schema", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--candidate-repository")
    parser.add_argument("--workflow-ref", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--tree-sha", required=True)
    args = parser.parse_args()
    try:
        predicate = json.loads(Path(args.predicate).read_text(encoding="utf-8"))
        import hashlib
        digest = "sha256:" + hashlib.sha256(
            Path(args.bundle_archive).read_bytes()
        ).hexdigest()
        result = verify_acceptance_handoff(
            predicate,
            expected_repository=args.repository,
            expected_candidate_repository=args.candidate_repository,
            expected_workflow_ref=args.workflow_ref,
            expected_commit_sha=args.commit_sha,
            expected_tree_sha=args.tree_sha,
            candidate_path=args.candidate,
            bundle_path=args.bundle,
            report_schema_path=args.report_schema,
            bundle_digest=digest,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, KeyError, ValueError) as exc:
        print(f"acceptance handoff verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
