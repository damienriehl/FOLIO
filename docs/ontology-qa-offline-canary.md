# Offline ontology QA canary

The offline canary consolidates the repository's deterministic ontology-QA
evidence before anyone attempts provider-backed qualification. It executes a
fixed, versioned pytest profile with network and unexpected child-process
guards. It neither contacts providers nor reads provider credentials.

## Prerequisites and invocation

Use Python 3.12 with the repository's existing development dependencies. The
command never installs packages and requires a destination that does not exist:

```bash
python scripts/run_offline_ontology_canary.py \
  --output-dir artifacts/offline-canary
```

Choose a new destination for every run. Existing directories, files, and
symlinks are refused and preserved. If a run is interrupted or incomplete,
retain it for diagnosis and choose a different destination when retrying.

## Outputs

- `report.json` is canonical JSON for automation. Its input fingerprint binds
  the result to the selected tests, QA implementation, policies, schemas,
  workflows, Python runtime, and relevant installed dependency versions.
- `summary.md` is the stable human-readable projection of that report.
- `raw/receipt.json`, `raw/junit.xml`, and `raw/pytest.log` are diagnostic
  execution evidence. They can contain volatile timing or local paths and are
  deliberately excluded from the stable report.

Exit code `0` means `passed`, `1` means a complete run observed assertion
failures, and `2` means `incomplete` (or a usage/publication error). Missing,
duplicated, skipped, expected-failure, contradictory, timed-out, or malformed
evidence is incomplete even when pytest otherwise succeeds.

## What a pass means

A pass establishes only that the checked-out implementation passed the fixed
offline fixture profile, including deterministic validation and delta logic,
qualification rules, release-decision behavior, evidence replay, the
full-policy trusted-runner fixture with stubbed independent providers, and
workflow contracts. Rejection fixtures passing demonstrates that unsafe inputs
are rejected; it does not claim that a current release was accepted.

The report therefore always records live provider qualification as `not_run`,
live GitHub Actions configuration as `not_verified`, and release authorization
as `false`. It does not assess current ontology quality. Provider-backed
qualification and the full live Actions canary remain separate work described
in [the Release A handoff](handoffs/2026-10-20-release-a-canary-and-qa-residuals.md)
and `NEXT-ONTOLOGY-QA.md`.
