# FOLIO-to-OpenGloss Mapping (R8) — Status

STATE: OpenGloss map 0-2-0; QA Release B awaits keys

Last updated: 2026-11-08

## What exists

The mapping set lives in `mappings/opengloss/`, beside `FOLIO.owl`, which this work never edits.

- **Mapping set:** `folio-opengloss.sssom.tsv`, an SSSOM TSV of 23,885 links over 5,192 senses (set 0.2.0). It links FOLIO classes to OpenGloss v2.4
  noun senses (revision `c64e480`), one SKOS mapping per row (exact, close, broad, related). The YAML
  header records the justification, confidence, tool, date, and both source versions.
- **Sidecars:** `senses.tsv` lists the linked senses. `gaps.tsv` lists FOLIO classes whose label is an
  OpenGloss headword but that got no link (a report for the OpenGloss maintainer).
- **Tooling:** under `scripts/`: builder, independent validator, OWL/SKOS/OntoLex exporter (output
  gitignored, about 22 MB), and gold-set scorer.
- **Heartbeat:** a weekly workflow regenerates the set when OpenGloss or `FOLIO.owl` changes. It writes
  a receipt and either merges or escalates.
- **Plan:** `docs/plans/2026-11-08-1830-feat-opengloss-mapping-module-plan.md`.

## Evidence

- **Determinism:** two builds from the same inputs are byte-identical.
- **Validation:** the validator passes against `FOLIO.owl`. Every subject exists and none is deprecated.
- **Quality:** 222 pairs, AI-judged with no human audit. Set 0.2.0 keys the domain prior to the FOLIO
  branch (plan `docs/plans/2026-11-08-2000-feat-opengloss-branch-aware-prior-plan.md`).
  - **Coverage:** 12,039 classes are now linked, up from 9,770.
  - **Recall:** recall of judged-correct pairs rose from 0.73 to 0.89.
  - **Precision:** estimated at 0.78 overall; the added links score 0.73.
  - **Keep rule:** passed on every condition.
- **Tests:** the suite runs offline without pyarrow, as CI does.
- **Review:** the code review returned "Ready with fixes" (one P1, eight P2). Its fixes were applied
  before merge in PR #16 (merge commit `4591b7e`).
- **Consumer:** folio-resolve pinned `4591b7e` and parsed the real file cleanly.

## Decisions (best practice, recorded)

- **Sense namespace:** sense IRIs use a provisional RFC 4151 tag URI
  (`tag:folio.openlegalstandard.org,2026:opengloss/sense/`) until OpenGloss publishes a namespace.
  Consumers read it from `curie_map`.
- **WordNet exclusion:** rows OpenGloss imports from Princeton WordNet are excluded, so the module quotes
  only CC BY 4.0 text.
- **Merge gate:** the heartbeat merges its own pull request when its in-job test run passes. `main` has
  no branch protection, and pull requests opened with the workflow token start no other workflows.

## Constraints and residual risks

- **Lexical method:** a `closeMatch` usually points at a sound sense, but its predicate is often not
  the best fit.
- **Heartbeat merge leg unexercised:** on 2026-11-08 a `workflow_dispatch` canary on `main` (run
  42516764717) queried Hugging Face, compared the `FOLIO.owl` hash, and reported "up to date". The
  pull-request-and-merge leg runs only when an upstream moves, so its first live run will be the
  first real upgrade.
- **Sameas defect:** the `owl:sameAs` restriction defect in `FOLIO.owl` is recorded in
  `docs/residual-review-findings/owl-sameas-restrictions.md`, not fixed here.
