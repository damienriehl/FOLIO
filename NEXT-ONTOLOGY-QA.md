# Automated Ontology QA — Next Actions

STATE: Release A complete — Release B awaits genuine cross-provider availability

- [ ] [P1] Run the real GitHub Actions canary when ready to publish Release A; `automated-ontology-qa` is already pushed to the `damienriehl/FOLIO` fork.
- [ ] [P1] Begin Release B only after two genuinely available independent model providers can complete the qualification path.
- [ ] [P2] Extract maintainability seams from `scripts/run_trusted_ontology_qa.py` without changing trusted-runner behavior.
- [ ] [P1] When `folio-python` 0.4.0 ships (alea-institute/folio-python#19), move `folio-python>=0.4.0` from `scripts/requirements-authoring.txt` into `scripts/requirements.txt` so `tests/test_iri_minting.py` gates CI instead of skipping.
- [ ] [P3] Normalise `xsd:string`-typed literals against plain ones in `compute_semantic_diff`. RDF 1.1 says `"x"` and `"x"^^xsd:string` denote the same literal, but rdflib set arithmetic treats them as distinct, so `R5RoVVyRmkyMepjXK7X1sp` is re-detected as a definition update on every run. The apply step rewrites identical bytes so the output is stable; this is summary noise, not churn.
- [ ] [P1] Resolve maintainer review on `alea-institute/FOLIO#16` and merge the Co-Investment Fund class after approval; Mike Bommarito's review is requested. The focused PR is one commit, one file, and does not carry the unpublished `automated-ontology-qa` work.
