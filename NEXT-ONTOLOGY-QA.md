# Automated Ontology QA — Next Actions

STATE: Release A complete — Release B awaits genuine cross-provider availability

- [ ] [P1] Push `automated-ontology-qa` and run the real GitHub Actions canary when ready to publish Release A.
- [ ] [P1] Begin Release B only after two genuinely available independent model providers can complete the qualification path.
- [ ] [P2] Extract maintainability seams from `scripts/run_trusted_ontology_qa.py` without changing trusted-runner behavior.
- [ ] [P1] When `folio-python` 0.4.0 ships (alea-institute/folio-python#19), move `folio-python>=0.4.0` from `scripts/requirements-authoring.txt` into `scripts/requirements.txt` so `tests/test_iri_minting.py` gates CI instead of skipping.
- [ ] [P2] Fix the silent no-op in `scripts/generate_webprotege_merge.py`: the definition apply regex matches a bare `<skos:definition>` but WebProtege writes `<skos:definition rdf:datatype="...#string">` for 9 of 15,664 definitions, so those updates are detected, never applied, and still counted by `print_summary`. `R5RoVVyRmkyMepjXK7X1sp` (No-Fault Claim) is currently diverged because of it.
