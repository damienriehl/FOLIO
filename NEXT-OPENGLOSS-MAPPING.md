# FOLIO-to-OpenGloss Mapping (R8) — Next Actions

STATE: OpenGloss map 0-2-0; QA Release B awaits keys

- [ ] [P2] Damien: send Mike Bommarito the drafted note asking OpenGloss to publish a sense and lexeme namespace, say whether sense indices stay stable across releases, and add a LICENSE file to opengloss-rs (the draft sits in this work's private handoff; it goes out in Damien's voice).
- [ ] [P2] Decide whether to offer the mapping module upstream to alea-institute/FOLIO, which is a maintainer-relationship call.
- [ ] [P3] Fix the 217 `owl:Restriction` on `owl:sameAs` crosswalks in `FOLIO.owl` as their own versioned change (see `docs/residual-review-findings/owl-sameas-restrictions.md`).
- [ ] [P3] Cut place-name noise in a later method version: in the `place` profile, require gloss overlap for word links inside proper names (judged errors: *Nam Dinh*, *Pando*, *Merida*, *Paul*), measured against `eval/gold.tsv` with the same keep rule.
