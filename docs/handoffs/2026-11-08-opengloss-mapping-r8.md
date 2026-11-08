---
artifact_contract: "ce-handoff/v1"
title: "FOLIO-to-OpenGloss mapping module (R8): planning checkpoint"
summary: "Resumed the R8 brief; format agreed with folio-resolve; plan and build not yet written."
keywords: ["opengloss", "sssom", "skos", "mapping", "R8"]
repository: "damienriehl/folio"
session: "b824c3ef-503a-5bae-b5d5-d7f7ef8605cb"
written_at: "2026-11-08T18:20:32.815Z"
head: "417a5e2ece96b011d4209986aa8a5a454c521cca"
branch: "feat/opengloss-mapping"
---

# FOLIO-to-OpenGloss mapping module (R8): checkpoint

## Objective

Publish a versioned FOLIO-to-OpenGloss mapping module beside `FOLIO.owl` (R8 of
lexplicit's plan `docs/plans/2026-11-08-1017-feat-opengloss-folio-anchoring-plan.md`,
on lexplicit branch `wip/opengloss-anchoring`). Additive only; `FOLIO.owl` is not edited.

## Decisions (Damien's, from the brief)

- **Location:** a separate module beside `FOLIO.owl`.
- **Mappings:** SKOS exact/close/broad/narrow/related match, one row per link;
  never delimited strings, an openGlossID field, `owl:equivalentClass` or `owl:sameAs`.
- **Qualifiers:** SSSOM mapping set; optional generated OWL module; OntoLex-Lemon senses.
- **Heartbeat:** regenerate with a receipt on upstream releases; ask Damien only on a
  schema change, a major version, or a score drop.

## Agreed with folio-resolve (consumer)

- **Path:** `mappings/opengloss/folio-opengloss.sssom.tsv`, plus a generated `.ttl` beside it.
- **Prefixes:** `FOLIO:` = `https://folio.openlegalstandard.org/`;
  `OGS:` = `tag:folio.openlegalstandard.org,2026:opengloss/sense/` (provisional RFC 4151
  tag URI; consumers read it from `curie_map`).
- **Rows:** sorted by subject, predicate, object; `semapv:LexicalMatching` justification.

## Current state

- Branch `feat/opengloss-mapping`, nothing committed yet beyond this file.
- OpenGloss v2.4 senses: 300,787 rows; columns include `domain`, `domain_root`,
  `lexeme_id`, `relations`; multiword sense IDs use underscores (`unverified_claim:adjective:0`).
- Confirmed the separate defect: 217 `owl:Restriction`s on `owl:sameAs` in `FOLIO.owl`.

## Next

1. Write the CE plan in `docs/plans/`.
2. Build generator, validator, OWL export, tests, docs, and heartbeat workflow.
3. Review, PR, merge; file the `owl:sameAs` issue; tell folio-resolve the merge commit.
