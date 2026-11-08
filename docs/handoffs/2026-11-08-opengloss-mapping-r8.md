---
artifact_contract: "ce-handoff/v1"
title: "FOLIO-to-OpenGloss mapping module (R8): planning checkpoint"
summary: "Plan committed; three Codex workers (U1 builder, U2 validator/export/score, U3 heartbeat) building in parallel; README written."
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

- Plan committed: `docs/plans/2026-11-08-1830-feat-opengloss-mapping-module-plan.md`.
- Codex workers U1 (builder), U2 (validator, OWL export, score), U3 (heartbeat, workflow) run in
  parallel in this worktree on disjoint files; task specs are in the cockpit's `agents/tasks/`
  as `folio-opengloss-u{1,2,3}-20261108.md`. Workers do not commit; the orchestrator does.
- `mappings/opengloss/README.md` written (counts to fill after the real build).
- Decision: exclude OpenGloss rows with `source == wordnet-3.0` (WordNet license); needs a
  follow-up filter in U1's loader.
- Confirmed the separate defect: 217 `owl:Restriction`s on `owl:sameAs` (18 PACER NoS classes);
  issue not yet filed.
- Baseline: 191 tests pass.

## Next

1. Integrate U1-U3, add the WordNet filter, run the real build under a memory cap, judge `eval/gold.tsv`.
2. Review (ce-code-review), fix, commit.
3. Review, PR, merge; file the `owl:sameAs` issue; tell folio-resolve the merge commit.
