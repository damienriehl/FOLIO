#!/usr/bin/env python3
"""Export an OpenGloss mapping set as deterministic Turtle annotations."""
from __future__ import annotations

import argparse
import sys

import yaml

from opengloss_mapping.owl_export import export


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tsv")
    parser.add_argument("--senses", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        count = export(args.tsv, args.senses, args.out)
    except (OSError, ValueError, KeyError, yaml.YAMLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {count} triples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
