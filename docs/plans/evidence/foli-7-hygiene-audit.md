# FOLIO maintainer hygiene audit receipt

Date: 2026-10-28 UTC
Starting commit: `c6089a1`
Environment: CPython 3.12.13, pip 26.1, Linux x86_64

## Disposition

**Dependency advisory audit: incomplete.** This is not a clean security result.
The isolated audit environment could not install `scripts/requirements-audit.txt`
because the package index was unreachable through the sandbox proxy. Therefore
`pip-audit 2.10.1` could not run, advisory coverage was not established, and no
claim about the absence of vulnerabilities is made. The normalized inventory in
`foli-7-dependencies.json` records the pre-provisioned environment in which the
suite was run; it is not a lockfile and was not successfully advisory-scanned.

Attempted command:

```text
python -m venv <temporary-directory>
<temporary-directory>/bin/python -m pip install -r scripts/requirements-audit.txt
```

Result: installation failed while resolving `rdflib`, after the proxy rejected
package-index connections. No audit JSON was produced. A maintainer should run
the commands in `CONTRIBUTING.md` in a network-enabled isolated environment and
replace this incomplete receipt with the resulting inventory and report.

## Test evidence

Before implementation, `python -m pip check` reported no broken requirements and
`python -m pytest tests -q -ra` passed 191 tests in 52.79 seconds. Final test
results are recorded in `STATUS-FOLI-7.md`.

Manifest SHA-256 values used for the final local checks:

```text
294114305a59df453c634732d5acbe1b471c0a853e9fca4e1b12ff3cc54ca2f5  scripts/requirements.txt
ccd942de399026853ad3e87c67ce0ae08c156811f048549ecb22b57059278aae  scripts/requirements-test.txt
1c3ccb9c60e378ed641684e19b53b56f4131530e1bbee312458269f8747a1d4b  scripts/requirements-audit.txt
```

## Bounded source review

Reviewed all four workflow files, `scripts/safe_extract_evidence_bundle.py`,
`scripts/verify_acceptance_handoff.py`, and `scripts/ontology_qa/providers/`.

- Pull-request deterministic code does not receive provider secrets; the
  provider-bearing workflow runs the protected checkout and treats candidate
  ontology bytes as data. Existing workflow contract tests retain that fence.
- Evidence extraction verifies the expected SHA-256 digest, rejects overwrite,
  validates every member before extraction, accepts only regular files and
  directories under `evidence/`, stages in a temporary directory, and publishes
  with one rename. New tests cover links, devices, roots, corruption, late unsafe
  members, and destination preservation.
- Acceptance verification binds the archive digest to the signed predicate and
  offline replay validates the bundle before merge generation.
- Provider adapters obtain keys only from their named environment variables,
  fail when absent, and return structured usage/response data; no credential
  values are included in their error messages. No shell subprocess construction
  was found in these adapters.

No source defect requiring a security-setting, credential, service, schema,
data, or deployment change was found in this bounded review. Hosted workflow
execution and a completed dependency advisory lookup remain external evidence.
