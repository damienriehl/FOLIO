# Automated Ontology QA follow-up work

Release A passed its offline verification contract on 2026-07-31. The
acceptance-focused review left these non-blocking follow-ups:

1. Extract the changed-record correction stage from
   `scripts/run_trusted_ontology_qa.py` into a focused `ontology_qa` module.
   Reuse the response-set and canonical-publication helpers shared with the
   confirmed-defect runner. Preserve the current single-directory atomic
   publication boundary and proposer-excluded verifier roles.
2. Run one GitHub Actions canary for the correction-to-fresh-SHA path. Verify
   that an artifact uploaded by the source trusted run is discoverable when
   the deterministic workflow for the correction commit completes, and that
   the automatic trigger restores the exact source, ledger, and evidence
   before dispatching the fresh immutable SHA.

Release B remains separately gated on genuine OpenAI/Google provider
availability and is not part of these offline follow-ups.
