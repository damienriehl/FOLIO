---
title: "feat: FOLIO-to-OpenGloss mapping module (R8)"
type: feat
status: active
date: 2026-11-08
origin: lexplicit docs/plans/2026-11-08-1017-feat-opengloss-folio-anchoring-plan.md (R8, R20), branch wip/opengloss-anchoring
---

# FOLIO-to-OpenGloss mapping module (R8)

## Goal

Publish a versioned mapping set that links FOLIO classes to OpenGloss word senses.
It sits beside `FOLIO.owl` and never edits it. Each link is one SKOS mapping, and each
link carries a justification, a confidence, the tool that made it, a date, and both
source versions. folio-resolve consumes it to type links between FOLIO hits and
OpenGloss hits on one span; lexplicit consumes it through folio-resolve.

## Decisions that bind this plan (Damien's, 2026-11-08)

- **Location:** a separate module beside `FOLIO.owl`, not inside its classes.
- **Predicates:** `skos:exactMatch`, `closeMatch`, `broadMatch`, `narrowMatch`,
  `relatedMatch`; one row per link, repeated for 1:many.
- **Forbidden:** delimited strings, an `openGlossID` field, `owl:equivalentClass`,
  `owl:sameAs`.
- **Qualifiers:** an SSSOM mapping set is the source of truth; an OWL annotation
  module is generated from it. Senses take the OntoLex-Lemon shape.
- **Claims, not facts:** every row records source, method, confidence, and dates.
- **Heartbeat:** the module regenerates automatically with a receipt when OpenGloss or
  FOLIO releases; Damien is asked only on a schema change, a major version, or a score drop.

## Decisions settled by best practice (this plan)

- **Sense IRIs: an RFC 4151 tag URI, provisional.** OpenGloss sense IDs
  (`breach:noun:1`) are not IRIs. The prefix `OGS:` expands to
  `tag:folio.openlegalstandard.org,2026:opengloss/sense/`; lexemes use `OGL:` =
  `tag:folio.openlegalstandard.org,2026:opengloss/lexeme/`. A tag URI is globally
  unique and owned by a domain the FOLIO project controls, yet resolves nowhere, so it
  creates no HTTP permanence obligation under `docs/FOLIO-CHANGE-POLICY.md` §2 and
  cannot be mistaken for an official OpenGloss namespace. When the OpenGloss
  maintainer publishes a namespace, only `curie_map` changes; the prefix names stay.
  Consumers must read the expansion from `curie_map`.
- **Set identifier:** `mapping_set_id` =
  `https://folio.openlegalstandard.org/mappings/opengloss`; the OWL module's version
  IRI appends the set version (`.../opengloss/0.1.0`). Neither path matches a FOLIO
  concept-IRI family, so neither can collide with a minted concept.
- **Method v0.1 is deterministic lexical matching with sense ranking.** No model
  call, no network, CPU only. Its confidence is an uncalibrated heuristic score, and
  the README says so.
- **Version scheme:** semver for the set. A minor bump for a regenerated set from new
  upstream data; a major bump for a format or method change that alters column
  meaning or the predicate rules.
- **The `owl:sameAs` restriction defect is filed, not fixed.** 217 classes in
  `FOLIO.owl` (219 matching lines, less 2 for the property's own declaration) use
  `owl:Restriction` on `owl:sameAs`. A GitHub issue records it; this plan copies none of it.

## Layout

```
mappings/opengloss/
  README.md                     format, method, provenance, namespace notice, consumer guide
  upstream.json                 pins: OpenGloss dataset+revision+sha256s+schema fingerprint; set version
  folio-opengloss.sssom.tsv     the mapping set (source of truth)
  folio-opengloss.ttl           generated OWL/SKOS/OntoLex module (committed if under ~10 MB, else a release artifact)
  gaps.tsv                      FOLIO terms whose OpenGloss headword lacks any legal sense (report for the maintainer)
  eval/gold.tsv                 hand-judged sample (agent judgment, labelled as such)
  receipts/<UTC-date>-<version>.json   one receipt per regeneration
scripts/opengloss_mapping/      library: folio loader, opengloss loader, matcher, writer, validator, owl export, score
scripts/build_opengloss_mappings.py      CLI: build the TSV (+gaps) from FOLIO.owl and parquet
scripts/validate_opengloss_mappings.py   CLI: validate a TSV (optionally against FOLIO.owl)
scripts/export_opengloss_owl.py          CLI: TSV -> TTL
scripts/opengloss_heartbeat.py           CLI: check upstreams, regenerate, score, write receipt, decide auto vs escalate
.github/workflows/opengloss-mapping-heartbeat.yml
tests/test_opengloss_*.py       fixture-driven; CI needs no parquet and no pyarrow
```

## SSSOM format (the contract with folio-resolve)

- **Header:** `#`-prefixed YAML with `curie_map` (`FOLIO`, `OGS`, `OGL`, `skos`,
  `semapv`, `rdfs`, `sssom`), `mapping_set_id`, `mapping_set_version`,
  `mapping_set_title`, `mapping_set_description`, `license`
  (`https://creativecommons.org/licenses/by/4.0/`), `mapping_date` (ISO date),
  `mapping_tool` (`scripts/build_opengloss_mappings.py`), `mapping_tool_version`
  (method version, `opengloss-lexical/0.1`), `subject_source`
  (`https://folio.openlegalstandard.org/`), `subject_source_version` (git commit of
  `FOLIO.owl` plus `sha256:` of the file), `object_source`
  (`https://huggingface.co/datasets/mjbommar/opengloss-v2.4-senses`),
  `object_source_version` (`<revision>`), and `extension_definitions` for any non-SSSOM column.
- **Columns, in this order:** `subject_id`, `subject_label`, `predicate_id`,
  `object_id`, `object_label`, `mapping_justification`, `confidence`,
  `subject_match_field`, `object_match_field`, `match_string`, `comment`.
  Set-level values (tool, versions, date, license) live in the header, per SSSOM's
  propagatable slots; a consumer that needs them per row propagates them.
- **Rows:** sorted by `subject_id`, then `predicate_id`, then `object_id`; unique per
  (subject, object), so one link carries one predicate; `confidence` in (0, 1] with
  three decimals; `mapping_justification` = `semapv:LexicalMatching`;
  `comment` names the rule that fired (`label-phrase`, `altlabel-phrase`, `head-word`,
  `modifier-word`) and the sense score.

## Method v0.1

1. **FOLIO surface forms:** for each non-deprecated `owl:Class`, take `rdfs:label`,
   `skos:prefLabel`, and English or untagged `skos:altLabel` (`en`, `en-us`, `en-gb`,
   untagged). Skip `skos:hiddenLabel` (misspellings and search aids). Normalize:
   casefold, NFKC, strip a trailing parenthetical qualifier (`License (Agreement)` →
   `license`), hyphens and slashes to spaces, collapse whitespace. A label with `/`
   (`Agreements / Contracts`) also yields each side as a form.
2. **OpenGloss index:** read only `sense_id`, `lexeme_id`, `headword`, `pos`,
   `sense_index`, `domain`, `domain_root`, `gloss`, filtered to headwords that equal a
   normalized form or a word in one. Keep `pos == noun` only (FOLIO classes are nominal).
3. **Sense score** for a (class, sense) pair, in [0, 1]:
   `0.5 * domain_prior + 0.5 * overlap`, where `domain_prior` is 1.0 for
   `law_government.*`, 0.7 for `business.*`, 0.3 otherwise, and `overlap` is the
   Jaccard overlap of content-word stems between the sense gloss and the class context
   (label, definition, and parent labels). A simple deterministic suffix stemmer and a
   fixed stop list are part of the method version.
4. **Phrase links:** when a whole normalized form equals a headword, the best-scoring
   sense becomes `skos:exactMatch` if its score ≥ 0.60 and it leads the runner-up by
   ≥ 0.10, from `rdfs:label`/`prefLabel`; otherwise `skos:closeMatch`. Any other
   sense of that headword scoring ≥ 0.55 becomes `skos:closeMatch`. Matches through an
   altLabel cap at `closeMatch`. Senses scoring below 0.45 never link.
5. **Word links (atoms):** for a label of 2-6 words, the head word (the first noun
   before `of`/`for`/`in`/`on`/`to`/`under`, else the last word) links its best sense by
   `skos:broadMatch`; other content words link by `skos:relatedMatch`. Each needs a
   sense score ≥ 0.50 and confidence = 0.8 × score. Word links remain even when a
   phrase link exists (R7: the phrase outranks its words, which stay as fallback evidence).
6. **Dedup:** per (subject, object), keep the strongest predicate
   (exact > close > broad = narrow > related), then the highest confidence.
7. **Gaps:** a FOLIO form whose headword exists in OpenGloss but has no noun sense in
   `law_government.*` or `business.*`, and that produced no link, goes to `gaps.tsv`
   (the `property` case), for the OpenGloss maintainer.
8. **Determinism:** ties break by `sense_id`; identical inputs give byte-identical output.

The thresholds are method constants, versioned with `mapping_tool_version`. Changing
one is a method change, so it bumps the method version and the set's major version.

## OWL module

`scripts/export_opengloss_owl.py` writes Turtle: an `owl:Ontology` with `owl:versionIRI`,
`owl:versionInfo`, `dcterms:license`, `dcterms:source` for both sources, and
`rdfs:comment` on the provisional namespace. Each row emits one SKOS triple
and one `owl:Axiom` (`owl:annotatedSource`, `owl:annotatedProperty`,
`owl:annotatedTarget`) carrying `sssom:confidence`, `sssom:mapping_justification`, and
`rdfs:comment`, which matches the SSSOM OWL serialization. Each object sense is an
`ontolex:LexicalSense` with `skos:definition` (gloss, CC BY 4.0, attributed) and
`ontolex:isSenseOf` its `OGL:` lexeme, an `ontolex:LexicalEntry` with
`ontolex:canonicalForm [ ontolex:writtenRep "<headword>"@en ]`. Only an `exactMatch` adds
`ontolex:reference` from the sense to the FOLIO class. The module does not
`owl:imports` FOLIO; it is an annotation layer.

## Validator (fails closed)

Checks: header keys present; `curie_map` covers every prefix used; predicates in the
five-SKOS allow-list; no forbidden predicate anywhere; no delimiter (`|`, `,`, `;`, space)
inside `object_id`; `object_id` matches `^OGS:[^:\s]+:[a-z]+:\d+$`; confidence range;
sort order; (subject, object) uniqueness; and, with `--folio FOLIO.owl`, every subject
exists and is not deprecated. The TTL exporter's output parses with rdflib and its SKOS
triple count equals the TSV row count.

## Score and heartbeat

- **Score:** `eval/gold.tsv` holds a judged sample of (subject, object, verdict, expected
  predicate) rows. The score is precision of emitted links on judged pairs, plus recall
  of pairs judged correct. The first gold set is an agent's judgment on a stratified
  sample, labelled as such in the file header; a human audit stays optional.
- **Heartbeat** (`opengloss_heartbeat.py`, weekly and on `workflow_dispatch`, plus on
  pushes to `main` that touch `FOLIO.owl`): compare the pinned OpenGloss revision with the
  Hugging Face API and detect newer `opengloss-v*` dataset series; compare `FOLIO.owl`'s
  hash with the header. If anything moved, download and verify the parquet, regenerate,
  validate, export, score, write a receipt, and open a PR. It escalates (label
  `heartbeat:needs-damien`, no auto-merge) on a schema-fingerprint change, a new major
  dataset series, or a precision drop above 0.02 or a link-count drop above 10%;
  otherwise it labels `heartbeat:auto` and requests auto-merge after its own tests pass.
- **Receipt:** JSON with old and new versions, row counts by predicate, score before
  and after, added and removed links (counts plus the first 50 of each), and the decision.

## Units

- **U1 (library + build CLI + tests):** surface forms, OpenGloss loader (pyarrow,
  authoring-only), matcher, writer, gaps; tests on fixtures (a small FOLIO RDF/XML
  fixture and a JSON sense fixture), including the Breach of Contract 1:many example,
  the property gap, altLabel capping, determinism.
- **U2 (validator + OWL export + tests):** depends only on the format above.
- **U3 (heartbeat + workflow + receipt + tests):** depends on the CLIs' interfaces;
  network calls injected so tests run offline.
- **U4 (generate + gold + docs):** run the real build under a memory cap, judge a
  sample into `eval/gold.tsv`, write `README.md`, a `NOTICES.md` attribution, and
  record the first receipt.
- **U5 (ship):** review, PR, merge, the `owl:sameAs` issue, the namespace-request
  draft for Damien, the message to folio-resolve, and the STATUS/NEXT files.

U1, U2, and U3 run in parallel on the shared format; U4 follows U1 and U2.

## Dependencies

- **pyarrow:** authoring-only, in `scripts/requirements-authoring.txt` (Apache-2.0).
  CI does not install it; tests never read parquet.
- **rdflib:** already a runtime dependency.

## Verification

- `python -m pytest tests -q` passes, including the existing suite.
- `python scripts/validate_opengloss_mappings.py mappings/opengloss/folio-opengloss.sssom.tsv --folio FOLIO.owl` exits 0.
- A second build from the same inputs is byte-identical.
- `FOLIO.owl` and `FOLIO-webprotege-merge-output.owl` are unchanged in the diff.

## Out of scope

- Editing `FOLIO.owl`, including the `owl:sameAs` defect.
- Model-assisted sense disambiguation (a later method version).
- Publishing an official OpenGloss namespace (the maintainer's call; a request is drafted).
