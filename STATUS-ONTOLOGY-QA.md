# Automated Ontology QA — Status

STATE: Release A complete — Release B awaits genuine cross-provider availability

Last updated: 2026-08-17

## Release A outcome

Release A is implemented on branch `automated-ontology-qa`.

- Changed-record corrections now run through the trusted QA runner.
- Correction outputs are staged and atomically published as one directory.
- Corrected ontologies receive deterministic final validation and dual-provider rereview.
- Fresh-SHA workflow handoff preserves and restores correction lineage.
- Automatic triggers recover the correction artifact and dispatch the corrected SHA.
- Offline replay loads review policy, honors correction lineage, and rejects tampered evidence.
- Workflow guards cover provenance, structured contracts, correction success/failure, and fresh-SHA replay.

## Verification

- Full suite: `128 passed in 13.70s`.
- Python compilation, workflow YAML parsing, and `git diff --check` passed.
- Production-shaped replay and tamper matrices passed.
- Independent-provider behavior is integration-tested with stubs; no live model calls were made.

## Commits

- `f20c0b4` — `feat(ontology): complete automated correction handoff`
- `928364e` — `docs(ontology): record Release A follow-ups`

## Constraints and residuals

- Release B depends on genuine cross-provider availability.
- Do not use Claude before Saturday morning, America/Chicago.
- Do not repeatedly retry OpenAI while the account has no credits.
- The two non-blocking residuals are a maintainability extraction from the large trusted-runner module and a real GitHub Actions canary.
- Detailed residual findings live in `docs/residual-review-findings/automated-ontology-qa.md`.
- `automated-ontology-qa` is pushed to `origin` (the `damienriehl/FOLIO` fork); no pull request has been opened against `alea-institute/FOLIO`.
- User-owned untracked files remain preserved.

## 2026-08-17 — Co-Investment Fund and IRI minting

- Added the `Co-Investment Fund` class (`R1cNH7TLMiSlSbIbdFsynUk`) under `Investment Funds`; commit `94e0e83`.
- Added `scripts/mint_iri.py`, which carries no generation logic and imports `folio.iri` from folio-python so there is one implementation; commit `f8dd90c`.
- Filed [alea-institute/folio-python#19](https://github.com/alea-institute/folio-python/pull/19), which moves the generator to `R` + base62, fixes a uniqueness check that could never fire, and removes a path that emitted local names shorter than the library's own assertion allows.
- `folio-python>=0.4.0` lives in `scripts/requirements-authoring.txt`, not `scripts/requirements.txt`, because that release is not on PyPI yet (latest published is 0.3.6) and an unresolvable pin there would take the fail-closed census down.
- Regenerated `FOLIO-webprotege-merge-output.owl`; commit `db354e1`.
- Found a pre-existing silent no-op in `scripts/generate_webprotege_merge.py` affecting 9 of 15,664 definitions; recorded in `NEXT-ONTOLOGY-QA.md`, not fixed here.
