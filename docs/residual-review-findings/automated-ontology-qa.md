# Automated Ontology QA follow-up work

Release A passed its offline verification contract on 2026-07-31. The
acceptance-focused review left these non-blocking follow-ups:

1. **Done 2026-10-03 (`5b935e8`).** Extract the changed-record correction stage from
   `scripts/run_trusted_ontology_qa.py` into a focused `ontology_qa` module.
   Reuse the response-set and canonical-publication helpers shared with the
   confirmed-defect runner. Preserve the current single-directory atomic
   publication boundary and proposer-excluded verifier roles.
2. Run one GitHub Actions canary for the correction-to-fresh-SHA path. Verify
   that an artifact uploaded by the source trusted run is discoverable when
   the deterministic workflow for the correction commit completes, and that
   the automatic trigger dispatches the fresh immutable SHA with the source-run
   inputs, and the fresh protected review restores the exact source, ledger,
   and evidence.

   **Local preparation completed 2026-10-26 (`foli-1`); live residual remains
   open.** Executable workflow tests now cover discovery/dispatch, provenance,
   restored bytes and arguments, missing files, correction ordering, and stale
   endpoints at publication/signing/check boundaries. Existing tests remain
   intact; full suite: 235 passed. The bounded live procedure and fixture are in
   `docs/ontology-qa-release-a-canary.md`. Full-size canonical-manifest runtime
   preflight is still unverified; full census, scoped delta, and single-change
   merge preparation cannot replace actual provider/Actions receipts. Provider
   access, authorized spend, existing approvals, and real accepted WebProtégé
   fidelity remain necessary to close this item.

Release B remains separately gated on genuine OpenAI/Google provider
availability and is not part of these offline follow-ups.
