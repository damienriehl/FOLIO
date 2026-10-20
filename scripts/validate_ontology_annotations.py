#!/usr/bin/env python3
"""Run the deterministic FOLIO annotation census."""

from __future__ import annotations

import argparse
import json
import sys

from ontology_qa.validators import validate_ontology


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ontology")
    parser.add_argument("--baseline")
    parser.add_argument("--policy", default="qa/ontology/review-policy.yaml")
    parser.add_argument("--shapes", default="qa/ontology/shapes.ttl")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = validate_ontology(
        args.ontology, policy_path=args.policy, shapes_path=args.shapes
    )
    if args.baseline:
        from ontology_qa.validators import compare_validation_results

        baseline = validate_ontology(
            args.baseline, policy_path=args.policy, shapes_path=args.shapes
        )
        result = compare_validation_results(baseline, result)
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
    if args.output:
        from pathlib import Path

        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
