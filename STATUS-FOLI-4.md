# FOLIO foli-4 - Offline QA Readiness

STATE: folio / foli-4 implementation complete; offline readiness command passes; live qualification remains separate.

Repository: `folio`
Item: `foli-4` (expansion)
Updated: 2026-10-27

## Completed work

Implemented the plan's fixed 68-case offline profile and a guarded runner that
creates a new output directory, records structured collection and JUnit
evidence, verifies mandatory proofs, fingerprints inputs before and after the
run, and publishes canonical JSON plus Markdown. The report explicitly leaves
live provider qualification, live Actions configuration, current ontology
quality, and release authorization unevaluated.

The subprocess receives an allowlisted environment, disables third-party
pytest plugin autoload, denies network connections, and permits only the known
offline replay child command. Existing outputs are refused without mutation.

Added report-contract, incomplete/failed precedence, reproducibility, input
identity, route-structure, preservation, and real-run regression coverage.
Documented invocation, outputs, interpretation, and recovery in
`docs/ontology-qa-offline-canary.md` and linked it from `README.md`.

## Evidence

- Baseline before implementation: `python -m pytest tests -q` — 191 passed.
- Focused feature suite: `python -m pytest tests/test_offline_canary.py -q` — 13 passed.
- Full suite after implementation: `python -m pytest tests -q` — 204 passed.
- Two fresh CLI runs produced byte-identical `report.json` and `summary.md`;
  each selected profile run passed 68 tests.

No ontology, policy, workflow, schema, provider route, credential, dependency,
release, or deployment configuration changed. No live service was contacted.

Cockpit's scanner is not present in this checkout, so controller-side
attribution verification for repository `folio` remains the sole continuity
action.
