# foli-6 - Usage documentation build status

STATE: foli-6 implementation complete; offline consumer guides and tested examples are ready.

Repository ID: `folio`

Item: `foli-6` (`expansion`)

Plan: [FOLIO Usage Examples and Documentation](docs/plans/2026-10-27-0953-feat-folio-usage-documentation-plan.md)

## Completed work

The README now links to delivered consumer documentation and runnable examples. The guides explain local setup, snapshot provenance, opaque identifiers, class and property subjects, label metadata, direct asserted hierarchy, anonymous restrictions, and deprecation semantics.

Three import-safe RDFLib examples load and summarize a local RDF/XML file, inspect a declared named class, and run a fixed bounded SELECT with an optional safely bound parent IRI. They produce deterministic Unicode JSON, reject URL-shaped ontology inputs, require no credentials or providers, and do not modify ontology bytes.

Focused tests cover fixtures, CLI failures, execution from another working directory, offline and byte-preserving loading, RDF term metadata, immediate hierarchy, unlabeled and deprecated classes, query binding and bounds, the published Investment Funds relation, and documentation links.

## Verification

The pre-change baseline passed: `python -m pytest tests -q` (191 passed).

The focused suite passed: `python -m pytest -q tests/test_consumer_examples.py tests/test_consumer_documentation.py` (11 passed).

All three documented commands ran successfully against `FOLIO.owl`. Its SHA-256 remained `c0f8ca58dad4227e89856d97a0344f45bec37289832837bd11c473dfdc7b44be` before and after.

No ontology, provider workflow, schema, deployment setting, release artifact, dependency bound outside the consumer example, or external service changed. This is not a frontend change, so screenshot evidence is inapplicable.

## Residual

The checkout documents Cockpit's `folio` assignment, but the external Cockpit scanner is unavailable here. Its actual attribution therefore remains a controller verification rather than a local claim.
