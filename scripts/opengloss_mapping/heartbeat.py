"""Model-free upstream checks, CLI regeneration, and review receipts."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Callable
from urllib.parse import quote
from urllib.request import urlopen

import yaml

API = 'https://huggingface.co/api/datasets'
SERIES_API = API + '?author=mjbommar&search=opengloss-v&limit=100'
SCRIPTS = {
    'build': 'scripts/build_opengloss_mappings.py',
    'validate': 'scripts/validate_opengloss_mappings.py',
    'export': 'scripts/export_opengloss_owl.py',
    'score': 'scripts/score_opengloss_mappings.py',
}


@dataclass(frozen=True)
class Check:
    opengloss_changed: bool
    folio_changed: bool
    dataset: str
    revision: str
    series: str
    parquet_files: tuple[str, ...]
    major_change: bool
    old_folio_sha256: str | None
    folio_sha256: str

    @property
    def moved(self) -> bool:
        return self.opengloss_changed or self.folio_changed


@dataclass(frozen=True)
class Result:
    exit_code: int = 0
    decision: str | None = None
    receipt: Path | None = None


def fetch_json(url: str):
    """Default injectable JSON transport."""
    with urlopen(url, timeout=120) as response:
        return json.load(response)


def download(url: str, dest: Path) -> None:
    """Default injectable binary transport."""
    with urlopen(url, timeout=120) as response, dest.open('wb') as output:
        shutil.copyfileobj(response, output)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def check(upstream: dict, folio_path: Path, current_tsv_header: dict,
          fetch_json: Callable) -> Check:
    """Inspect both upstreams without changing local files."""
    pinned = upstream['opengloss']
    version = tuple(map(int, pinned['series'].split('.')))
    candidates = []
    for item in fetch_json(SERIES_API):
        match = re.fullmatch(r'mjbommar/opengloss-v(\d+)\.(\d+)-senses', item.get('id', ''))
        if match and tuple(map(int, match.groups())) > version:
            candidates.append((tuple(map(int, match.groups())), item['id']))
    target_version, dataset = max(candidates) if candidates else (version, pinned['dataset'])
    info = fetch_json(f'{API}/{dataset}')
    revision = info['sha']
    files = tuple(sorted(item['rfilename'] for item in info.get('siblings', [])
                         if item['rfilename'].endswith('.parquet')))
    old_hash = re.search(r'sha256:([a-fA-F0-9]{64})', str(current_tsv_header.get('subject_source_version', '')))
    old_hash = old_hash.group(1).lower() if old_hash else None
    folio_hash = sha256(Path(folio_path))
    return Check(dataset != pinned['dataset'] or revision != pinned['revision'],
                 folio_hash != old_hash, dataset, revision,
                 '.'.join(map(str, target_version)), files, target_version[0] > version[0],
                 old_hash, folio_hash)


def read_tsv(path: Path) -> tuple[dict, list[dict]]:
    with path.open(encoding='utf-8') as stream:
        lines = stream.readlines()
    header = yaml.safe_load('\n'.join(line[1:] for line in lines if line.startswith('#'))) or {}
    rows = list(csv.DictReader(io.StringIO(''.join(line for line in lines if not line.startswith('#'))), delimiter='\t'))
    return header, rows


def fingerprint(path: Path) -> str:
    # Authoring-only dependency; checking a heartbeat never imports pyarrow.
    import pyarrow.parquet as pq
    schema = '\n'.join(f'{field.name}:{field.type}' for field in pq.read_schema(path))
    return 'sha256:' + hashlib.sha256(schema.encode('utf-8')).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def triples(rows: list[dict]) -> set[str]:
    return {' '.join(row[key] for key in ('subject_id', 'predicate_id', 'object_id')) for row in rows}


def number(value) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def run(repo_root: Path | str = '.', *, fetch_json: Callable = fetch_json,
        download: Callable = download, scripts: dict | None = None,
        parquet_dir: Path | None = None, schema_fingerprint: Callable = fingerprint,
        dry_run: bool = False, output_decision: Path | None = None,
        now: datetime | None = None) -> Result:
    """Regenerate through the four public CLIs; preserve receipts on CLI failure.

    ``parquet_dir`` can supply the pinned local parquet cache for a FOLIO-only
    rebuild. Otherwise missing cache files are fetched at their pinned revision.
    CLI script paths may be overridden individually, including by absolute paths.
    """
    root = Path(repo_root).resolve()
    base = root / 'mappings/opengloss'
    pins_path = base / 'upstream.json'
    tsv_path = base / 'folio-opengloss.sssom.tsv'
    old = json.loads(pins_path.read_text(encoding='utf-8'))
    header, before_rows = read_tsv(tsv_path)
    folio = root / old.get('folio', {}).get('path', 'FOLIO.owl')
    state = check(old, folio, header, fetch_json)
    if dry_run:
        print(json.dumps({**asdict(state), 'moved': state.moved}, sort_keys=True))
        return Result()
    if not state.moved:
        print('up to date')
        return Result()
    timestamp = now or datetime.now(timezone.utc)
    timestamp = timestamp.astimezone(timezone.utc)
    date = timestamp.date().isoformat()
    new = deepcopy(old)
    major, minor, _ = map(int, old['set_version'].split('.'))
    new['set_version'] = f'{major}.{minor + 1}.0'
    og = new['opengloss']
    og.update(dataset=state.dataset, revision=state.revision, series=state.series)
    reasons = []
    if state.major_change:
        reasons.append('major series changed')
    cli = {**SCRIPTS, **(scripts or {})}
    def invoke(name: str, *args: str) -> subprocess.CompletedProcess:
        result = subprocess.run([sys.executable, str(root / cli[name]), *map(str, args)],
                                cwd=root, text=True, capture_output=True, check=False)
        if result.returncode:
            print(f'{name}: {result.stderr}', file=sys.stderr)
        return result
    exit_code = 0
    after_rows = before_rows
    score_after = None
    with tempfile.TemporaryDirectory(prefix='opengloss-heartbeat-') as temp:
        stage = Path(temp)
        if state.opengloss_changed:
            if not state.parquet_files:
                raise ValueError('target dataset has no parquet files')
            parquet = stage / 'parquet'
            files = [{'path': path} for path in state.parquet_files]
        else:
            parquet = Path(parquet_dir) if parquet_dir else root / '.cache/opengloss' / state.revision
            files = deepcopy(og['files'])
        if len({PurePosixPath(item['path']).name for item in files}) != len(files):
            raise ValueError('parquet basenames must be unique for the build CLI')
        for item in files:
            relative = PurePosixPath(item['path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError(f'unsafe parquet path: {relative}')
            dest = parquet / relative.name
            if state.opengloss_changed or not dest.is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                url = (f'https://huggingface.co/datasets/{state.dataset}/resolve/'
                       f'{quote(state.revision, safe="")}/{quote(str(relative), safe="/")}')
                download(url, dest)
            digest = sha256(dest)
            if not state.opengloss_changed and digest != item['sha256'].removeprefix('sha256:'):
                raise ValueError(f'pinned parquet hash mismatch: {relative}')
            item['sha256'] = digest
        if state.opengloss_changed:
            og['files'] = files
            og['schema_fingerprint'] = schema_fingerprint(parquet / PurePosixPath(files[0]['path']).name)
        if og['schema_fingerprint'] != old['opengloss']['schema_fingerprint']:
            reasons.append('schema fingerprint changed')
        staged_pins = stage / 'upstream.json'
        write_json(staged_pins, new)
        staged_tsv = stage / tsv_path.name
        senses = stage / 'senses.tsv'
        gaps = stage / 'gaps.tsv'
        ttl = stage / 'folio-opengloss.ttl'
        build = invoke('build', '--folio', folio, '--parquet-dir', parquet,
                       '--upstream', staged_pins, '--out', staged_tsv,
                       '--senses-out', senses, '--gaps-out', gaps, '--mapping-date', date)
        if build.returncode:
            reasons.append('build failed')
            exit_code = 1
        else:
            _, after_rows = read_tsv(staged_tsv)
            validation = invoke('validate', staged_tsv, '--folio', folio)
            if validation.returncode:
                reasons.append('validation failed')
                exit_code = 1
            export = invoke('export', staged_tsv, '--senses', senses, '--out', ttl)
            if export.returncode:
                reasons.append('export failed')
                exit_code = 1
            score = invoke('score', staged_tsv, '--gold', base / 'eval/gold.tsv', '--json')
            try:
                if score.returncode:
                    raise ValueError('score CLI failed')
                score_after = json.loads(score.stdout)
                if not isinstance(score_after, dict):
                    raise ValueError('score must be an object')
            except (ValueError, json.JSONDecodeError):
                reasons.append('score failed')
                exit_code = 1
            for path in (staged_tsv, senses, gaps, ttl):
                if path.exists():
                    shutil.copyfile(path, base / path.name)
    score_before = old.get('score', {})
    old_precision = score_before.get('precision')
    new_precision = (score_after or {}).get('precision')
    if number(old_precision) and number(new_precision) and old_precision - new_precision > .02 + 1e-12:
        reasons.append('precision fell by more than 0.02')
    if len(after_rows) < len(before_rows) * .9:
        reasons.append('row count fell by more than 10%')
    new['score'] = score_after if score_after is not None else {'precision': None, 'recall': None, 'judged': 0}
    decision = 'needs-damien' if reasons else 'auto'
    added = sorted(triples(after_rows) - triples(before_rows))
    removed = sorted(triples(before_rows) - triples(after_rows))
    pair = lambda before, after: {'before': before, 'after': after}
    receipt = {
        'generated_at': timestamp.isoformat(), 'decision': decision, 'reasons': reasons,
        'set_version': pair(old['set_version'], new['set_version']),
        'opengloss': pair({k: old['opengloss'][k] for k in ('dataset', 'revision')},
                         {k: og[k] for k in ('dataset', 'revision')}),
        'folio_sha256': pair(state.old_folio_sha256, state.folio_sha256),
        'schema_fingerprint': pair(old['opengloss']['schema_fingerprint'], og['schema_fingerprint']),
        'rows': pair(len(before_rows), len(after_rows)),
        'rows_by_predicate': pair(dict(Counter(row['predicate_id'] for row in before_rows)),
                                  dict(Counter(row['predicate_id'] for row in after_rows))),
        'score': pair(score_before, score_after),
        'added': {'count': len(added), 'sample': added[:50]},
        'removed': {'count': len(removed), 'sample': removed[:50]},
    }
    receipt_path = base / 'receipts' / f'{date}-{new["set_version"]}.json'
    write_json(pins_path, new)
    write_json(receipt_path, receipt)
    if output_decision is not None:
        output_decision = Path(output_decision)
        output_decision.parent.mkdir(parents=True, exist_ok=True)
        output_decision.write_text(decision + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return Result(exit_code, decision, receipt_path)
