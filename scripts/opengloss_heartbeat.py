#!/usr/bin/env python3
"""Check OpenGloss/FOLIO releases and regenerate the mapping module."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from opengloss_mapping.heartbeat import run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path('.'))
    parser.add_argument('--dry-run', action='store_true', help='Check only and print JSON')
    parser.add_argument('--output-decision', type=Path)
    args = parser.parse_args()
    try:
        return run(args.repo_root, dry_run=args.dry_run,
                   output_decision=args.output_decision).exit_code
    except (OSError, ValueError, KeyError) as exc:
        print(f'heartbeat: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
