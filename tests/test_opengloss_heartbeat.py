"""Offline heartbeat contracts, including the subprocess boundary."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from opengloss_mapping.heartbeat import check, run


STUB = '''import json, pathlib, sys
args = sys.argv[1:]
root = pathlib.Path(__file__).parent
config = json.loads((root / "config.json").read_text())
name = pathlib.Path(__file__).stem
with (root / "calls").open("a") as f: f.write(name + "\\n")
if name == "build":
    pathlib.Path(args[args.index("--out")+1]).write_text(config["tsv"])
    for flag in ("--senses-out", "--gaps-out"):
        pathlib.Path(args[args.index(flag)+1]).write_text("header\\n")
elif name == "validate": sys.exit(config.get("validation", 0))
elif name == "export": pathlib.Path(args[args.index("--out")+1]).write_text("# turtle\\n")
elif name == "score": print(json.dumps(config["score"]))
'''


def tsv(n=10, replacement=False):
    ids = range(1, n + 1) if replacement else range(n)
    return ('# subject_source_version: "git:old sha256:' + hashlib.sha256(b'folio').hexdigest()
            + '"\nsubject_id\tpredicate_id\tobject_id\n' + ''.join(
                f'FOLIO:{i}\tskos:closeMatch\tOGS:sense:noun:{i}\n' for i in ids))


@pytest.fixture
def repo(tmp_path):
    base = tmp_path / 'mappings/opengloss'
    base.mkdir(parents=True)
    (tmp_path / 'FOLIO.owl').write_bytes(b'folio')
    (base / 'folio-opengloss.sssom.tsv').write_text(tsv())
    upstream = json.loads((Path(__file__).parent / 'fixtures/opengloss/heartbeat/upstream.json').read_text())
    (base / 'upstream.json').write_text(json.dumps(upstream))
    scripts = {}
    for name in ('build', 'validate', 'export', 'score'):
        scripts[name] = tmp_path / f'{name}.py'
        scripts[name].write_text(STUB)
    (tmp_path / 'config.json').write_text(json.dumps({'tsv': tsv(replacement=True), 'score': {
        'precision': .9, 'recall': .8, 'judged': 10, 'rows': 10,
        'rows_by_predicate': {'skos:closeMatch': 10}}}))
    downloads = []
    def fetch(url):
        if '?' in url:
            return [{'id': upstream['opengloss']['dataset']}]
        return {'sha': 'new', 'siblings': [{'rfilename': 'data/train.parquet'}, {'rfilename': 'README.md'}]}
    def download(url, dest):
        downloads.append(url)
        Path(dest).write_bytes(b'parquet')
    return tmp_path, upstream, scripts, fetch, download, downloads


def execute(repo, **kwargs):
    root, _, scripts, fetch, download, _ = repo
    return run(root, fetch_json=fetch, download=download, scripts=scripts,
               schema_fingerprint=lambda path: 'sha256:same', **kwargs)


def test_up_to_date_writes_nothing(repo, capsys):
    root, upstream, scripts, _, download, downloads = repo
    def fetch(url):
        return [] if '?' in url else {'sha': 'old', 'siblings': []}
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    result = run(root, fetch_json=fetch, download=download, scripts=scripts)
    assert result.exit_code == 0 and result.receipt is None
    assert 'up to date' in capsys.readouterr().out
    assert before == {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert downloads == []


def test_revision_auto_receipt(repo):
    result = execute(repo)
    assert result.decision == 'auto'
    receipt = json.loads(result.receipt.read_text())
    assert receipt['added']['count'] == receipt['removed']['count'] == 1
    assert receipt['added']['sample'] == ['FOLIO:10 skos:closeMatch OGS:sense:noun:10']
    assert receipt['set_version'] == {'before': '0.1.0', 'after': '0.2.0'}
    assert receipt['rows'] == {'before': 10, 'after': 10}
    assert receipt['opengloss']['after']['revision'] == 'new'
    assert receipt['generated_at'].endswith('+00:00')
    assert (repo[0] / 'calls').read_text().splitlines() == ['build', 'validate', 'export', 'score']
    pins = json.loads((repo[0] / 'mappings/opengloss/upstream.json').read_text())
    assert pins['method_version'] == repo[1]['method_version']
    assert pins['opengloss']['files'][0]['sha256'] == hashlib.sha256(b'parquet').hexdigest()


def test_schema_change(repo):
    root, _, scripts, fetch, download, _ = repo
    result = run(root, fetch_json=fetch, download=download, scripts=scripts,
                 schema_fingerprint=lambda path: 'sha256:changed')
    assert result.decision == 'needs-damien'
    assert 'schema fingerprint changed' in json.loads(result.receipt.read_text())['reasons']


def test_major_series(repo):
    root, _, scripts, _, download, _ = repo
    def fetch(url):
        return [{'id': 'mjbommar/opengloss-v3.0-senses'}, {'id': 'mjbommar/opengloss-v2.9-senses'}] if '?' in url else {
            'sha': 'new', 'siblings': [{'rfilename': 'train.parquet'}]}
    result = run(root, fetch_json=fetch, download=download, scripts=scripts,
                 schema_fingerprint=lambda path: 'sha256:same')
    receipt = json.loads(result.receipt.read_text())
    assert result.decision == 'needs-damien'
    assert receipt['opengloss']['after']['dataset'].endswith('v3.0-senses')


@pytest.mark.parametrize(('change', 'reason'), [
    ({'precision': .85}, 'precision fell by more than 0.02'),
    ({'n': 8}, 'row count fell by more than 10%'),
    ({'validation': 1}, 'validation failed'),
])
def test_escalations(repo, change, reason):
    path = repo[0] / 'config.json'
    config = json.loads(path.read_text())
    if 'precision' in change: config['score']['precision'] = change['precision']
    if 'n' in change: config['tsv'] = tsv(change['n'])
    if 'validation' in change: config['validation'] = change['validation']
    path.write_text(json.dumps(config))
    result = execute(repo)
    assert result.decision == 'needs-damien'
    assert reason in json.loads(result.receipt.read_text())['reasons']
    assert result.exit_code == (1 if 'validation' in change else 0)


def test_folio_only_reuses_verified_cache(repo):
    root, upstream, scripts, _, download, downloads = repo
    (root / 'FOLIO.owl').write_bytes(b'changed')
    cache = root / 'cached'
    cache.mkdir()
    (cache / 'train.parquet').write_bytes(b'parquet')
    def fetch(url):
        return [] if '?' in url else {'sha': 'old', 'siblings': []}
    result = run(root, fetch_json=fetch, download=download, scripts=scripts, parquet_dir=cache)
    assert result.decision == 'auto'
    assert downloads == []
    receipt = json.loads(result.receipt.read_text())
    assert receipt['folio_sha256']['after'] == hashlib.sha256(b'changed').hexdigest()


def test_workflow_contract():
    source = (Path(__file__).parents[1] / '.github/workflows/opengloss-mapping-heartbeat.yml').read_text()
    workflow = yaml.safe_load(source)
    triggers = workflow.get('on', workflow.get(True))
    assert triggers['schedule'] == [{'cron': '17 7 * * 1'}]
    assert 'workflow_dispatch' in triggers
    assert triggers['push'] == {'branches': ['main'], 'paths': ['FOLIO.owl']}
    assert workflow['permissions'] == {'contents': 'write', 'pull-requests': 'write'}
    assert workflow['concurrency']['group'] == 'opengloss-mapping-heartbeat'
    assert workflow['concurrency']['cancel-in-progress'] is False
    assert 'secrets.' not in source
    assert 'GH_TOKEN: ${{ github.token }}' in source
    assert 'gh pr merge --auto --squash' in source
    assert '--output-decision' in source
    steps = workflow['jobs']['heartbeat']['steps']
    assert {step['uses'] for step in steps if 'uses' in step} == {
        'actions/checkout@v4', 'actions/setup-python@v5'}
    assert steps[0]['with']['fetch-depth'] == 0
    assert steps[1]['with']['python-version'] == '3.12'
    assert 'git config user.name \'github-actions[bot]\'' in source
    assert 'gh label create' in source and '--force' in source


def test_minor_series_selects_highest_and_ignores_other_datasets(repo):
    root, upstream, _, _, _, _ = repo
    def fetch(url):
        if '?' in url:
            return [{'id': value} for value in [
                'mjbommar/opengloss-v2.5-senses', 'mjbommar/opengloss-v2.12-senses',
                'other/opengloss-v9.0-senses', 'mjbommar/opengloss-v20.0-lexemes']]
        assert url.endswith('mjbommar/opengloss-v2.12-senses')
        return {'sha': 'minor', 'siblings': [{'rfilename': 'a.parquet'}, {'rfilename': 'README.md'}]}
    state = check(upstream, root / 'FOLIO.owl', {
        'subject_source_version': 'sha256:' + hashlib.sha256(b'folio').hexdigest()}, fetch)
    assert state.moved and state.opengloss_changed and not state.folio_changed
    assert state.series == '2.12' and not state.major_change
    assert state.parquet_files == ('a.parquet',)


def test_dry_run_is_check_only(repo, capsys):
    root, _, scripts, fetch, download, downloads = repo
    decision = root / 'decision'
    before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    result = run(root, fetch_json=fetch, download=download, scripts=scripts,
                 dry_run=True, output_decision=decision)
    assert result.exit_code == 0
    assert json.loads(capsys.readouterr().out)['moved'] is True
    assert downloads == [] and not decision.exists()
    assert before == {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_exact_thresholds_do_not_escalate_and_decision_written(repo):
    root = repo[0]
    config_path = root / 'config.json'
    config = json.loads(config_path.read_text())
    config['tsv'] = tsv(9)
    config['score']['precision'] = .88
    config_path.write_text(json.dumps(config))
    decision_path = root / 'decision'
    result = execute(repo, output_decision=decision_path)
    assert result.decision == 'auto'
    assert decision_path.read_text() == 'auto\n'


def test_unjudged_score_does_not_escalate(repo):
    path = repo[0] / 'config.json'
    config = json.loads(path.read_text())
    config['score']['precision'] = None
    path.write_text(json.dumps(config))
    assert execute(repo).decision == 'auto'


def test_diff_samples_are_limited_to_fifty(repo):
    root = repo[0]
    (root / 'mappings/opengloss/folio-opengloss.sssom.tsv').write_text(tsv(100))
    path = root / 'config.json'
    config = json.loads(path.read_text())
    config['tsv'] = tsv(100).replace('FOLIO:', 'FOLIO:new')
    path.write_text(json.dumps(config))
    receipt = json.loads(execute(repo).receipt.read_text())
    assert receipt['added']['count'] == receipt['removed']['count'] == 100
    assert len(receipt['added']['sample']) == len(receipt['removed']['sample']) == 50


def test_cli_help_exposes_workflow_interface():
    result = subprocess.run([sys.executable, str(Path(__file__).parents[1] /
                            'scripts/opengloss_heartbeat.py'), '--help'],
                            capture_output=True, text=True)
    assert result.returncode == 0
    assert all(flag in result.stdout for flag in ('--repo-root', '--dry-run', '--output-decision'))
