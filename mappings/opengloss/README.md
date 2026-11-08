# FOLIO-to-OpenGloss mapping set

This module links FOLIO classes to word senses in
[OpenGloss](https://huggingface.co/datasets/mjbommar/opengloss-v2.4-senses), an open
English lexicon. It sits beside `FOLIO.owl` and never changes it: FOLIO classes keep their
meaning, and OpenGloss senses keep theirs. The mapping set only records typed links between them.

Every link is a **claim, not a fact**. A deterministic lexical matcher made each one, and
each records how it was made, how confident the matcher was, and which versions of FOLIO and
OpenGloss it read.

## Files

| File | What it holds |
|---|---|
| `folio-opengloss.sssom.tsv` | The mapping set, in [SSSOM](https://mapping-commons.github.io/sssom/) TSV. **Source of truth.** |
| `senses.tsv` | Every OpenGloss sense the set links to: id, lexeme, headword, part of speech, domain, gloss. |
| `folio-opengloss.ttl` | The same links as an OWL annotation module (SKOS triples, SSSOM axiom annotations, OntoLex-Lemon senses). Generated from the two files above and not committed, because it runs about 22 MB; build it with `scripts/export_opengloss_owl.py`. |
| `gaps.tsv` | FOLIO classes whose label is an OpenGloss headword but which got no link, with that headword's senses and domains. A report for the OpenGloss maintainer. |
| `eval/gold.tsv` | A judged sample of links, used to score each regeneration. |
| `upstream.json` | Pins: the OpenGloss dataset, revision, file hashes, and schema fingerprint; the set and method versions; the last score. |
| `receipts/` | One JSON receipt per regeneration: what changed, the score, and the upgrade decision. |

## Reading the mapping set

Each row is one link: `subject_id` (a FOLIO class), `predicate_id` (a SKOS mapping
property), and `object_id` (one OpenGloss sense). One FOLIO class often links to several
senses, so it gets several rows. A row never packs two senses into one field.

| Predicate | Meaning here |
|---|---|
| `skos:exactMatch` | The sense names the same concept as the FOLIO class. |
| `skos:closeMatch` | The sense is close enough to use for the class in many contexts. |
| `skos:broadMatch` | The sense is broader than the class. *Breach of Contract* `broadMatch` *breach* (failure to fulfill an obligation). |
| `skos:narrowMatch` | The sense is narrower than the class. |
| `skos:relatedMatch` | The sense names a word inside the class's label. *Breach of Contract* `relatedMatch` *contract*. |

The set never uses `owl:sameAs` or `owl:equivalentClass`. Both assert logical identity,
which a lexical match cannot support.

**Phrases and words.** A multiword FOLIO label links to its phrase sense when OpenGloss has
one, and also to the senses of its words: the head word by `broadMatch`, the other content
words by `relatedMatch`. A tagger should prefer the phrase link and keep the word links as
fallback evidence.

**Confidence.** `confidence` is the matcher's heuristic score, from 0 to 1. It ranks links
against each other; it is not a calibrated probability. `eval/gold.tsv` measures how often
the links are right.

**Columns.** `mapping_justification` is `semapv:LexicalMatching` on every row.
`subject_match_field` names the FOLIO label that matched (`rdfs:label`, `skos:prefLabel`, or
`skos:altLabel`), and `match_string` the normalized text. `comment` names the rule that
fired (`label-phrase`, `altlabel-phrase`, `head-word`, `modifier-word`) and the sense score.
Set-wide values (license, date, tool and method version, both source versions) live in the
YAML header, per SSSOM.

**TSV dialect.** Every TSV here is tab-separated with no quoting: no field contains a tab or a
newline, and a label may contain a literal `"`. Read it with
`csv.DictReader(lines, delimiter="\t", quoting=csv.QUOTE_NONE)` on the lines after the `#` header.

## Sense identifiers are provisional

OpenGloss publishes sense ids such as `breach:noun:1`, which are not IRIs. Until OpenGloss
publishes a namespace, this set uses provisional [tag URIs](https://www.rfc-editor.org/rfc/rfc4151)
that resolve nowhere:

```
OGS: tag:folio.openlegalstandard.org,2026:opengloss/sense/    (senses)
OGL: tag:folio.openlegalstandard.org,2026:opengloss/lexeme/   (lexemes)
```

**Consumers must read the expansion from the header's `curie_map`, not hard-code it.** When
OpenGloss publishes a namespace, the expansion changes and the prefix names `OGS` and `OGL`
stay. To recover a raw OpenGloss id, strip the `OGS:` prefix from `object_id`.

## How good the links are

`eval/gold.tsv` holds 162 judged pairs: 25 emitted links per predicate, plus every candidate sense
of 30 unlinked classes. An AI agent judged them from the glosses and FOLIO definitions alone; no
human has audited them. Against set version 0.1.0:

| Predicate | Judged correct | Judge chose the same predicate |
|---|---:|---:|
| `skos:exactMatch` | 24 of 25 | 14 of 24 |
| `skos:closeMatch` | 20 of 25 | 2 of 20 |
| `skos:broadMatch` | 15 of 24 | 12 of 15 |
| `skos:relatedMatch` | 17 of 23 | 16 of 17 |

Overall precision on the judged links is 0.78, and the set emits 73% of the pairs the judge called
correct. (The sample was drawn before a tokenization fix, so 3 sampled links no longer appear.)
Each regeneration rescores against this file, and `upstream.json` keeps the latest score. Two readings follow. An `exactMatch` is a strong anchor. A `closeMatch` usually points at a
sound sense, but its predicate is a placeholder: the judge most often wanted `broadMatch`,
`narrowMatch`, or `exactMatch` instead, which a lexical method cannot tell apart. Treat it as
"related sense, kind of relation unknown".

## How the links are made (method `opengloss-lexical/0.1`)

1. **FOLIO forms:** each non-deprecated class's `rdfs:label`, `skos:prefLabel`, and English
   `skos:altLabel`s, normalized: case folded, a trailing parenthetical qualifier removed,
   hyphens and slashes read as spaces. Hidden labels are skipped.
2. **Candidates:** OpenGloss noun senses (from OpenGloss itself, not its WordNet imports)
   whose headword equals a form, or a word in one.
3. **Score:** half a domain prior (law and government 1.0, business 0.7, other 0.3), half
   the share of the gloss's content words that also appear in the class's label, definition,
   or parent labels. This is how *tenant* the renter wins over *tenant* the software customer.
4. **Links:** the best phrase sense becomes `exactMatch` when it scores at least 0.60 and
   leads the runner-up by 0.05; otherwise `closeMatch`. A match through an altLabel stops at
   `closeMatch`. Word links need a score of at least 0.45. Senses below 0.40 never link.

The method is deterministic: the same inputs give byte-identical files. The thresholds belong
to the method version, and changing one is a method change.

## Regenerating

```bash
python -m pip install -r scripts/requirements-authoring.txt   # adds pyarrow
python scripts/build_opengloss_mappings.py --parquet-dir <dir with train-0000N.parquet> \
    --out mappings/opengloss/folio-opengloss.sssom.tsv \
    --senses-out mappings/opengloss/senses.tsv --gaps-out mappings/opengloss/gaps.tsv
python scripts/validate_opengloss_mappings.py mappings/opengloss/folio-opengloss.sssom.tsv --folio FOLIO.owl
python scripts/export_opengloss_owl.py mappings/opengloss/folio-opengloss.sssom.tsv \
    --senses mappings/opengloss/senses.tsv --out mappings/opengloss/folio-opengloss.ttl
python scripts/score_opengloss_mappings.py mappings/opengloss/folio-opengloss.sssom.tsv \
    --gold mappings/opengloss/eval/gold.tsv
```

The builder checks every parquet file against the sha256 in `upstream.json` before reading it.

## Heartbeat

`.github/workflows/opengloss-mapping-heartbeat.yml` runs weekly, on demand, and whenever
`FOLIO.owl` changes on `main`. If OpenGloss published a new revision or series, or `FOLIO.owl`
changed, it regenerates the set, validates and scores it, writes a receipt, and opens a pull
request.

- **Upgrades on its own** (label `heartbeat:auto`, merged by the workflow) when the checks pass.
- **Waits for a maintainer** (label `heartbeat:needs-damien`) on an OpenGloss schema change, a
  new major OpenGloss series, a failed validation, a precision drop above 0.02, or a drop of more
  than 10% in links.

A pull request opened with the workflow token does not start other workflows, so the heartbeat
runs the test suite itself and treats that run as the merge gate. It keeps one heartbeat pull request
open at a time, and a failed run changes no mapping file: its pull request carries only the receipt.

## Versioning

The set uses semantic versioning. A regeneration from new upstream data is a minor version.
A change to the method or to what a column means is a major version.

## License and attribution

The mapping set is CC BY 4.0, like FOLIO.

`senses.tsv` and the generated Turtle quote headwords and glosses from OpenGloss by Michael J.
Bommarito II, from the OpenGloss v2.4 release
(<https://huggingface.co/collections/mjbommar/opengloss-2x>; paper:
<https://arxiv.org/abs/2511.18622>), licensed under the Creative Commons Attribution 4.0
International license (CC BY 4.0, <https://creativecommons.org/licenses/by/4.0/>). Changes: rows
filtered to the senses this set links to, and columns reduced to those listed above; no text
was edited.

The matcher reads only OpenGloss's own senses. It skips the rows OpenGloss imports from
Princeton WordNet 3.0 (`source = wordnet-3.0`), so no WordNet text appears here.
