# Automated Ontology QA — Next Actions

STATE: Release A complete — Release B awaits genuine cross-provider availability

- [ ] [P1] Push `automated-ontology-qa` and run the real GitHub Actions canary when ready to publish Release A.
- [ ] [P1] Begin Release B only after two genuinely available independent model providers can complete the qualification path.
- [ ] [P2] Extract maintainability seams from `scripts/run_trusted_ontology_qa.py` without changing trusted-runner behavior.
- [ ] [P1] When `folio-python` 0.4.0 ships (alea-institute/folio-python#19), move `folio-python>=0.4.0` from `scripts/requirements-authoring.txt` into `scripts/requirements.txt` so `tests/test_iri_minting.py` gates CI instead of skipping.
- [ ] [P1] Fix definition *additions* in `scripts/generate_webprotege_merge.py`: when FOLIO.owl gains a second `skos:definition`, the apply path replaces the existing one instead of appending, destroying it. Reproduced with a two-definition class; 87 classes in FOLIO.owl already carry more than one definition, so the shape is real. Detection (`new_defs and not removed_defs`) is correct; only the apply step conflates add with replace.
- [ ] [P1] Open a focused PR to `alea-institute/FOLIO` for the Co-Investment Fund class. It cannot ride `automated-ontology-qa`, which is 29 commits ahead of `upstream/main` and carries unpublished Release A work. `FOLIO.owl` differs from `upstream/main` by exactly the 29 lines of the new class, so a clean branch off `upstream/main` is straightforward.

