#!/usr/bin/env python3
"""Assemble or replay a durable FOLIO ontology QA evidence bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ontology_qa.replay import replay_bundle
from ontology_qa.reporting import ArtifactBundle, build_release_report


def read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--report-schema", default="schemas/ontology-qa-report.schema.json")
    parser.add_argument("--baseline")
    parser.add_argument("--candidate")
    for name in ("manifest", "census", "primary", "independent", "primary-qualification", "independent-qualification", "reconciliation", "surveillance"):
        parser.add_argument(f"--{name}")
    parser.add_argument("--run-id", default="local")
    parser.add_argument("--attempt-id", default="1")
    parser.add_argument("--policy-hash", default="unconfigured")
    parser.add_argument("--tool-hash", default="unconfigured")
    args = parser.parse_args()
    try:
        if args.replay:
            result = replay_bundle(args.bundle, report_schema_path=args.report_schema)
        else:
            required = ("baseline", "candidate", "manifest", "census", "primary", "independent", "primary_qualification", "independent_qualification", "reconciliation", "surveillance")
            missing = [name for name in required if not getattr(args, name)]
            if missing:
                raise ValueError(f"missing assembly inputs: {', '.join(missing)}")
            stages = {name: read_json(getattr(args, name)) for name in ("manifest", "census", "primary", "independent", "surveillance")}
            report = build_release_report(
                **stages,
                primary_qualification=read_json(args.primary_qualification),
                independent_qualification=read_json(args.independent_qualification),
                reconciliation=read_json(args.reconciliation),
                run_id=args.run_id, attempt_id=args.attempt_id,
                policy_hash=args.policy_hash, tool_hash=args.tool_hash,
            )
            bundle = ArtifactBundle(args.bundle)
            for name, artifact in stages.items():
                bundle.publish_json(name, artifact)
            bundle.publish_qualification("primary_qualification", read_json(args.primary_qualification))
            bundle.publish_qualification("independent_qualification", read_json(args.independent_qualification))
            bundle.publish_json("report", report)
            bundle.snapshot("baseline.owl", args.baseline)
            bundle.snapshot("candidate.owl", args.candidate)
            bundle.publish_index(report)
            result = replay_bundle(args.bundle, report_schema_path=args.report_schema)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError) as exc:
        print(f"ontology QA failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
