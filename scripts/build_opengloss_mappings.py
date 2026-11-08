#!/usr/bin/env python3
"""Build deterministic SSSOM mappings from FOLIO and pinned OpenGloss senses."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
from pathlib import Path
import subprocess

from opengloss_mapping.folio_forms import load_folio
from opengloss_mapping.matcher import candidate_headwords, match
from opengloss_mapping.senses import load_json, load_parquet, sha256_file
from opengloss_mapping.sssom_writer import CURIE_MAP, MAPPING_SET_ID, write_gaps, write_senses, write_sssom


def folio_version(path: Path) -> str:
    digest = 'sha256:' + sha256_file(path)
    try:
        result = subprocess.run(['git', 'log', '-1', '--format=%H', '--', path.resolve().name], cwd=path.resolve().parent, capture_output=True, text=True, check=True)
        commit = result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = ''
    return f'{commit}; {digest}' if commit else digest


def make_header(upstream: dict, mapping_date: str, version: str) -> dict:
    og = upstream['opengloss']
    return dict(
        curie_map=CURIE_MAP,
        mapping_set_id=MAPPING_SET_ID,
        mapping_set_version=upstream['set_version'],
        mapping_set_title='FOLIO–OpenGloss lexical mappings',
        mapping_set_description='These links are lexical-matching claims between FOLIO classes and OpenGloss senses, with an uncalibrated heuristic confidence rather than a probability of correctness. The OGS: and OGL: namespaces are provisional FOLIO-owned identifiers, pending an official OpenGloss namespace.',
        license='https://creativecommons.org/licenses/by/4.0/',
        mapping_date=mapping_date,
        mapping_tool='https://github.com/alea-institute/FOLIO/blob/main/scripts/build_opengloss_mappings.py',
        mapping_tool_version=upstream['method_version'],
        subject_source=CURIE_MAP['FOLIO'],
        subject_source_version=version,
        object_source='https://huggingface.co/datasets/' + og['dataset'],
        object_source_version=og['dataset'] + '@' + og['revision'],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folio', type=Path, default=Path('FOLIO.owl'))
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument('--parquet-dir', type=Path)
    sources.add_argument('--senses-json', type=Path)
    parser.add_argument('--upstream', type=Path, default=Path('mappings/opengloss/upstream.json'))
    parser.add_argument('--out', type=Path, default=Path('mappings/opengloss/folio-opengloss.sssom.tsv'))
    parser.add_argument('--senses-out', type=Path, default=Path('mappings/opengloss/senses.tsv'))
    parser.add_argument('--gaps-out', type=Path, default=Path('mappings/opengloss/gaps.tsv'))
    parser.add_argument('--mapping-date', type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument('--folio-version')
    args = parser.parse_args()
    try:
        upstream = json.loads(args.upstream.read_text(encoding='utf-8'))
        classes = load_folio(args.folio)
        headwords = candidate_headwords(classes)
        senses = load_json(args.senses_json, headwords) if args.senses_json else load_parquet(args.parquet_dir, upstream, headwords)
        rows, gaps = match(classes, senses)
        header = make_header(upstream, args.mapping_date.isoformat(), args.folio_version or folio_version(args.folio))
        write_sssom(args.out, header, rows)
        write_senses(args.senses_out, senses, rows)
        write_gaps(args.gaps_out, gaps)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f'OpenGloss build failed: {exc}\n')
    counts = Counter(r['predicate_id'] for r in rows)
    predicates = ', '.join(f'{key}={counts[key]}' for key in sorted(counts)) or 'none'
    print(f'rows={len(rows)} ({predicates}); senses={len({r["object_id"] for r in rows})}; gaps={len(gaps)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
