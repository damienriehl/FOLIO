# foli-2 Provider Qualification Build Receipt

STATE: Offline Release B qualification correctness is implemented and verified; live qualification remains open.

## Built

The evaluator now keeps correction answer keys private, scores both complete rounds, compares exact proposer replacements, and counts only actual defect verdicts as detections. Fresh and cached receipts must bind the dispatched request and exact observed provider/model before cache publication or qualification. Trusted replay reconstructs frozen production and correction cases and recomputes role-specific metrics and qualification status.

No ontology bytes, corpus, schema, dependency, deployment setting, production data, or credentials changed.

## Verification

- Pre-change baseline: `pytest -q` — 191 passed in 50.12s.
- Focused changed suites: `pytest -q tests/test_model_evals.py tests/test_model_qualification.py tests/test_review_execution.py tests/test_model_review.py tests/test_correction_evidence.py tests/test_evidence_replay.py tests/test_trusted_changed_record_corrections.py` — 60 passed in 2.66s.
- Final verification: `python -m compileall -q scripts tests && git diff --check && pytest -q` — all checks passed; 205 tests passed in 49.74s.

## Live gate not run

No provider-backed qualification ran. Release B still requires authorized access and bounded spend for all six roles: production primary, production independent, benchmark adjudicator, correction proposer, and two independent correction verifiers. Evidence must retain frozen inputs, two complete rounds, observed identities, request bindings, thresholds, role separation, budgets, and successful offline replay. Cache-only or fixture results do not prove present availability.

The neutral numeric controls demonstrate number-preservation mechanics, not broad legal-language competence. Source-grounded language coverage remains a separate prerequisite for broader claims.

The controller must reconcile the unavailable chief campaign source and verify that Cockpit attributes these top-level files to repository `folio`.
