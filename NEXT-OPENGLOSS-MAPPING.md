# FOLIO-to-OpenGloss Mapping (R8) — Next Actions

STATE: OpenGloss map 0-2-0; QA Release B awaits keys

- [ ] [P2] Damien: send Mike Bommarito the drafted note asking OpenGloss to publish a sense and lexeme namespace, say whether sense indices stay stable across releases, and add a LICENSE file to opengloss-rs (the draft sits in this work's private handoff; it goes out in Damien's voice).
- [ ] [P2] Decide whether to offer the mapping module upstream to alea-institute/FOLIO, which is a maintainer-relationship call.
- [ ] [P2] Decide with FOLIO's maintainers how to retire the class restrictions on `rdfs:seeAlso` (3,677), `rdfs:locatedIn` (231), `owl:sameAs` (217) and `owl:isAuthor` (6): it needs a coordinated folio-python release, because folio-python reads the seeAlso pattern (see `docs/residual-review-findings/owl-sameas-restrictions.md`).
- [ ] [P3] Cut place-name noise in a later method version with referent evidence: match the country or region in a Location class's parent labels against each sense's gloss. A structural rule (one sense per place name) was tested and rejected on 2026-11-08, because half of the dropped sibling senses were valid; see `docs/plans/2026-11-08-2130-fix-opengloss-place-sibling-senses-plan.md`.
