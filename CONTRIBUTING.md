# Contributing to FOLIO

Use Python 3.12 for the deterministic contributor checks. Install the declared
test environment rather than assembling test dependencies ad hoc:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r scripts/requirements-test.txt
python -c "import folio.iri"
python -m pip check
python -m pytest tests -q -ra
```

The import check is intentional: the IRI drift tests must not disappear behind
a missing optional dependency. The full suite also expects `FOLIO.owl` and
`FOLIO-webprotege-merge-output.owl` in the repository root.

## Ontology checks

An absolute census reports all current defects and can fail because of known
legacy debt:

```bash
python scripts/validate_ontology_annotations.py FOLIO.owl --output census.json
python scripts/mint_iri.py --audit
```

For a change, compare the candidate to the exact baseline ontology. Known,
unchanged failures are reported as legacy debt, while newly introduced failures
block the command:

```bash
git show <baseline-commit>:FOLIO.owl > baseline.owl
python scripts/validate_ontology_annotations.py FOLIO.owl \
  --baseline baseline.owl --output deterministic-census.json
```

Generate permanent concept IRIs with `scripts/mint_iri.py`; do not type them.
See `docs/FOLIO-CHANGE-POLICY.md` before changing published ontology content.

## Offline evidence replay

After separately verifying and extracting a downloaded evidence archive, replay
the bundle without provider access:

```bash
python scripts/run_ontology_hydration_qa.py --bundle evidence --replay \
  --report-schema schemas/ontology-qa-report.schema.json
```

Replay validates retained snapshots, hashes, lineage, and report structure. It
does not call providers and does not replace the protected provider-backed
review used for ontology corrections.

## Dependency audit

The audit manifest includes the tested packages and pins the audit tool. It
requires package-index and PyPI advisory network access, so run it in a fresh
isolated environment where that access is available:

```bash
python -m venv .audit-venv
. .audit-venv/bin/activate
python -m pip install -r scripts/requirements-audit.txt
python -m pip check
python -m pytest tests -q -ra
python -m pip_audit --strict --vulnerability-service pypi \
  --format json --output pip-audit.json
```

Do not describe an audit as clean if installation, advisory lookup, or package
coverage is incomplete. The dated repository receipt records the exact local
result and its limitations.
