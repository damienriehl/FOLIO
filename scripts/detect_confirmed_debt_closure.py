#!/usr/bin/env python3
"""Report confirmed debt closed between immutable ontology endpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ontology_qa.debt import closed_debt, load_debt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--debt", required=True, type=Path)
    args = parser.parse_args()
    ids, roots = closed_debt(
        args.baseline, args.candidate, load_debt(args.debt)
    )
    print(json.dumps({
        "closed_count": len(ids),
        "closed_debt_ids": ids,
        "root_record_ids": sorted(roots),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
