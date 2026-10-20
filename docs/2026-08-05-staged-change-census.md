# Census of staged FOLIO changes — 2026-08-05

_Every change currently staged against `FOLIO.owl`, classified against `docs/FOLIO-CHANGE-POLICY.md`. Baseline: `FOLIO.owl` at commit `e36f3f8` (`main` == `origin/main` == `upstream/main` == `a8f0d29`; working tree byte-identical to HEAD). **No ontology artifact was modified to produce this document** — all analysis is read-only._

## Headline

| | |
|---|---:|
| Staged rows/triples inventoried | **151,122** |
| **T0 Fill** — safe to ship today | **109,236** |
| **T1 Enrich** — safe, but each needs a collision decision | **6,138** |
| **Invalid SKOS** — must be fixed, not tiered | **2** |
| **T2 Revise** — needs a version boundary | **12** |
| **T3 Restructure** — 2 additive, 14 removals | **16** |
| **T4 Reidentify** | **0** |
| Quarantined by content gates, not yet tier-classifiable | 35,718 |

_Reconciliation: 115,360 (digest KEEP) + 35,718 (digest REGENERATE) + 16 (hidden labels) + 16 (tribal edits) + 12 (confirmed defects) = 151,122._

**Nothing staged is T4.** No pending change deletes a class, changes an IRI, merges two IRIs, or reuses an IRI. The "merging nodes" concern that prompted this work is not present in anything staged — the one duplicate concept FOLIO has (`RCiAtR0akBA7apMyfjy515B`) was already resolved by deprecation-in-place in commit `e36f3f8`, with the IRI retained.

Three things are nonetheless riskier than they were being treated as. They are §5.

---

## 1. Baseline — what `FOLIO.owl` contains today

```bash
# stdlib iterparse over FOLIO.owl; full script in the session scratchpad
python3 parse_folio.py
```

| Measure | Count |
|---|---:|
| `owl:Class` declarations | 18,327 |
| Classes with a `skos:definition` | 15,414 |
| Classes with **no** `skos:definition` | 2,913 |
| Classes with an **empty-string** `skos:definition` | 12 |
| Classes with `owl:deprecated` | 3 |
| Classes with ≥1 `skos:example` | 486 |
| Classes with >1 asserted parent | 832 |
| `skos:hiddenLabel` triples | 5,117 |
| `skos:altLabel` triples | 57,333 |
| Transitive `rdfs:subClassOf` pairs | 99,264 |
| Distinct surface forms in the OntoKit-indexed label space | 75,340 |
| …of those, already ambiguous (resolve to >1 concept) | 1,716 |

**The ontology header declares no version at all** — only `dc:title` and `dc:description`. No `owl:versionIRI`, `owl:versionInfo`, `owl:priorVersion`, `dcterms:issued`, or `dcterms:license`. See the policy, §3.

### FOLIO has never removed an IRI

```bash
for c in $(git log --reverse --format=%h -- FOLIO.owl); do
  git show "$c:FOLIO.owl" | grep -oP '(?<=<owl:Class rdf:about=")[^"]+' | sort -u > "$c.iris"
done   # then comm -23 consecutive pairs
```

18 commits have touched `FOLIO.owl`. Class count went 18,324 → 18,327, monotonically. **Class IRIs removed across the entire published history: 0.** IRI permanence is already FOLIO's practice; the policy only writes it down.

The history does contain three non-monotone (T2) commits, shipped with no version bump and no changelog because there was no mechanism for either:

| Commit | Change | Tier |
|---|---|---|
| `8f35bc6` | Stripped the `folio:` prefix from 125 `rdfs:label` and 47 `skos:prefLabel` values, moving them to `skos:notation` (212 added) | T2 |
| `2a18e1e` | `Rules of Civil Procedure` definition: "criminal actions" → "civil actions" | T2 |
| `e36f3f8` | Removed `skos:altLabel "Agreement"` from `License (Agreement)`; deprecated the duplicate class | T2 + deprecation |

---

## 2. The write-back digest — `digest-0001-partition`

Source: `generative-folio/docs/writeback/digest-0001-partition/payload/`. 151,078 input rows, partitioned into `keep.jsonl` (115,360) and `regenerate.jsonl` (35,718). Row shape: `{iri, label, branch, component, predicate, lang, value}`.

### 2.1 The Tier 0 / Tier 1 question, measured

The brief's expectation was that some generated definitions would replace existing ones (T2) and others would fill empty slots (T0). **The data says the split is not where it was expected to be.** Cross-referencing every row against the parsed `FOLIO.owl`:

| Check | KEEP | REGENERATE |
|---|---:|---:|
| Rows | 115,360 | 35,718 |
| Rows whose IRI is absent from `FOLIO.owl` | **0** | **0** |
| `skos:definition` rows | **0** | 2,920 |
| `skos:altLabel` rows | 100,530 | 29,869 |
| `skos:example` rows | 14,830 | 2,929 |
| altLabel rows landing in an already-occupied `(predicate, lang)` slot | **0** | — |
| altLabel rows exactly duplicating an existing altLabel | **0** | — |
| example rows on a class that already has an example | **0** | — |

**`keep.jsonl` contains zero definitions.** Every one of the 2,920 generated definitions failed gate `G1-grounding` and went to `regenerate.jsonl`. And `G1-grounding` fails precisely when *the concept has no `skos:definition` in FOLIO to anchor generation* — so:

> **The groundedness gate and the blast-radius tier point in opposite directions on the same rows.** A definition written into an empty slot is the *safest possible* change to ship (T0 — no consumer can observe a regression) and simultaneously the *least trustworthy* content in the digest (nothing anchored the generation). Conversely, the rows that are best-grounded are alt-labels and examples on already-defined concepts, which are also structurally harmless.

This is why the policy insists (§7 step 5) that tier and correctness are independent axes. Of the 2,920 proposed definitions, **2,907 fill a genuinely empty slot**, **12 sit over an empty-string `skos:definition`** (a latent data defect in `FOLIO.owl` — see §5.3), and **exactly one is a true T2 replacement over real text**: `RCaMM3whpuSnuFNtCOupTex` *Financial Sponsor*, which currently carries an M&A-specific definition and would be replaced with a general one. All 2,920 are quarantined behind the gates regardless.

### 2.2 The KEEP payload, tiered

Every KEEP row lands in an empty slot, so the tier turns entirely on the *collision check* from policy §1: after the change, does the surface form resolve to exactly one concept?

| | Rows | Tier |
|---|---:|---|
| `skos:example` — all slots empty, no lookup ambiguity possible | 14,830 | **T0** |
| `skos:altLabel` — string resolves to exactly 1 concept after the change | 94,394 | **T0** |
| `skos:altLabel` — string resolves to >1 concept after the change | 6,136 | **T1** |
| **Total** | **115,360** | |

Of the 6,136 T1 rows, 320 collide with a surface form already held by a different FOLIO concept; the remainder collide with each other inside the batch. The effect on the label space:

| | Today | After KEEP |
|---|---:|---:|
| Ambiguous surface forms | 1,716 | **4,760** |

That is a 2.8× increase in label ambiguity — the exact class of problem commit `e36f3f8` was written to fix. It does not make the digest unsafe; it means 6,136 rows need the collision decision that policy §1 requires, and 109,224 do not.

### 2.3 Coverage the KEEP payload would deliver

| Language | altLabels today | KEEP adds | After |
|---|---:|---:|---:|
| de-de | 5,450 | 9,795 | 15,245 |
| en-gb | 5,008 | 10,281 | 15,289 |
| es-es | 4,969 | 10,266 | 15,235 |
| es-mx | 4,970 | 10,278 | 15,248 |
| fr-fr | 5,450 | 9,775 | 15,225 |
| he-il | 4,994 | 10,292 | 15,286 |
| hi-in | 4,988 | 10,240 | 15,228 |
| ja-jp | 5,450 | 9,904 | 15,354 |
| pt-br | 5,450 | 9,780 | 15,230 |
| zh-cn | 5,450 | 9,919 | 15,369 |
| **Total** | **52,179** | **100,530** | **152,709** |

Examples: 486 classes have one today; KEEP would give a first example to **14,830 more**.

The `en-gb` column carries the known duplicate-label policy (ruling q2). Measured against the actual KEEP rows: **4,599 of 10,281 en-gb additions are case-folded-identical to the concept's own `rdfs:label`**, of which 2,848 are byte-identical. Under q2 these are intentional and are not defects; the number is recorded here because it is 45% of the en-gb payload and it accounts for a large share of the T1 ambiguity above.

### 2.4 The REGENERATE payload

35,718 rows quarantined by the content gates. **These are not tier-classifiable yet** — the values will change when they are regenerated, so any collision or grounding check run against today's strings is void. They are excluded from the safe-to-ship list on content grounds, not blast-radius grounds. Structurally they are the same shape as KEEP: 0 rows target a missing IRI, 0 land in an occupied slot.

---

## 3. The 14 tribal/language re-parentings — T3

`folio` branch `fix/tribal-language-branch-conflict` (`717aa8a`); source `generative-folio` `12979b1`; proposal at `generative-folio/docs/writeback/tribal-fix/PROPOSAL.md`. **Currently HELD by Damien's ruling q4 pending an OntoKit view. Nothing here disturbs that hold.**

Diff against `main`: **2 insertions, 14 deletions**, `rdfs:subClassOf` resource lines only. No labels, definitions, or IRIs touched.

| Operation | Concepts | Tier |
|---|---:|---|
| Drop the tribal parent edge, keep `Language` | 12 | **T3 removal** |
| Re-parent `Caddo` → `American Indian Tribes (Continental US)` | 2 | **T3 removal + addition** |

Simulated against the parsed hierarchy:

| Parent | Descendants today | After | Lost |
|---|---:|---:|---:|
| American Indian Tribes (Continental United States) | 614 | 606 | 8 |
| Native Alaskan Tribes | 271 | 267 | 4 |
| Caddo | 2 | 0 | 2 |

- Classes whose ancestor set changes: **16** (the 14, plus the 2 descendants of `Caddo`).
- Concepts left with zero parents: **none** — every one of the 12 retains its `Language` parent.
- Transitive `rdfs:subClassOf` pairs: **99,264 → 99,212, a net −52** (0.052% of the closure).

**What a consumer observes.** Anyone who materialised the closure and stored it holds 52 stale rows, silently. Anyone faceting on the *Governmental Body* branch loses 12 members from their result set. Anyone querying `Language` descendants is unaffected. The absolute blast radius is small and precisely bounded — but it is non-monotone, so under the policy it is a MAJOR boundary.

**The escape valve applies to part of it.** Policy §4 valve 1: the two `Caddo` re-parentings can ship *additively* today — add `subClassOf American Indian Tribes (Continental US)` without removing `subClassOf Caddo` — which places both concepts correctly, retracts nothing, and leaves them temporarily double-parented in an ontology that already has 832 multi-parented classes. The removal waits for the boundary. The other 12 have no additive form, because the removal *is* the fix.

---

## 4. The 16 Agreements `skos:hiddenLabel` candidates — T0/T1, with 4 defects

`folio` branch `add-synonyms-appellate-appeal` (`bf78c78`), targeting `R88D8i8AcSTUig2X3yPbFHg` (`rdfs:label` "Agreements", `skos:prefLabel` "Contracts"). All 16 are bare literals with no `xml:lang`.

**Merge result verified non-destructively:**

```bash
git merge-tree --write-tree main add-synonyms-appellate-appeal   # -> 4bf0ece
git diff main 4bf0ece --stat -- FOLIO.owl                        # 16 insertions(+), 0 deletions
```

The merge is genuinely additive: **+16 triples, 1 class, 0 deletions.** (See §5.1 for why `git diff main..branch` says otherwise and why that matters.)

Running the two mechanical checks from policy §7 step 4 against every term:

| Term | Already an `altLabel` on this class? | Already resolves to another concept? | Verdict |
|---|:--:|---|---|
| Agreement | **yes** | — | **Invalid — SKOS S13** |
| Contract | **yes** | — | **Invalid — SKOS S13** |
| Covenant | no | **yes — `Obligation`** | **T1 — needs a decision** |
| Indenture | no | **yes — `Indenture`** | **T1 — needs a decision** |
| Accord, Accords, Pacts, Covenants, Compact, Compacts, Pact, Undertaking, Undertakings, Indentures, Concordat, Concordats | no | no | **T0 — ship** |

**Two of the sixteen are invalid SKOS, not merely low-tier.** `Agreement` and `Contract` already exist as `skos:altLabel` on this exact class — they were added by commit `e36f3f8`, the Agreement precision fix. Asserting the same literal, with the same (absent) language tag, on the same subject under both `skos:altLabel` and `skos:hiddenLabel` violates SKOS Reference §5.2 integrity condition **S13**, which declares the three labelling properties pairwise disjoint. A SKOS validator will flag it. They are also pointless: `altLabel` already covers the term, and OntoKit indexes `altLabel`.

**Two more create new ambiguity.** `Covenant` currently resolves to `Obligation`; `Indenture` currently resolves to a concept named `Indenture`. Adding them here makes each string resolve to two concepts — reproducing, in miniature, the exact bug `e36f3f8` was written to fix.

The remaining **12 are clean T0** and can ship on merge.

### What hidden labels are worth in the first place

`ontokit-api/ontokit/services/ontology_index.py` defines `LABEL_PROPERTIES` as `rdfs:label`, `skos:prefLabel`, `skos:altLabel`, `dcterms:title`, `dc:title`. **`skos:hiddenLabel` is not indexed.** FOLIO already carries 5,117 hidden labels, and none of them is retrievable in FOLIO's own viewer.

The implication is not that hidden labels are worthless — SKOS defines `hiddenLabel` precisely for search-only forms (misspellings, deprecated jargon) that should match a query but never be displayed, which is exactly what "Concordat" or "Undertakings" is for. The implication is that **the value of all hidden-label work, past and future, is currently zero in the one consumer FOLIO controls, and unlocking it is a one-line change in OntoKit** — adding `SKOS.hiddenLabel` to that list. Doing so retroactively activates 5,117 existing triples plus these 12. Shipping more hidden labels *before* that change adds triples nothing reads.

---

## 5. Riskier than assumed

### 5.1 A stale branch makes an additive change look destructive — and vice versa

`add-synonyms-appellate-appeal` branches from `8f35bc6` and is **18 commits behind `main`**, 10 of which touched `FOLIO.owl`. Consequently:

| Measurement | Result |
|---|---|
| `git diff main..add-synonyms-appellate-appeal --stat` | **25 insertions, 134 deletions** |
| `git merge-tree --write-tree main <branch>`, then diff | **16 insertions, 0 deletions** |

The merge is correct and safe. But the tree difference includes reverting everything `main` gained since the branch point, and a maintainer who resolves the branch by *checking it out and taking its `FOLIO.owl`* — a normal-looking action on an 18 MB single-file repo — would silently revert all 10 of those `FOLIO.owl` commits, including:

- re-adding `skos:altLabel "Agreement"` to `License (Agreement)`, undoing the precision fix;
- restoring `rdfs:label "DUPE of \`License \`"` and dropping `owl:deprecated`, **un-deprecating a deprecated concept**;
- restoring the `Rules of Civil Procedure` definition to "criminal actions".

None of it would error, and the file would still parse. This is now policy §7 step 6: **classify against the merge result, never against the branch.**

### 5.2 There is a T2 change staged that was not on anyone's list

`folio/qa/ontology/confirmed-defects.json` — 12 entries, all `"state": "open"`, 12 distinct subjects, sourced from `docs/2026-07-29-published-content-audit.md`. **These are the only staged changes that rewrite live published text**, and they were not part of the framing of this question.

| Predicate | Count | Defect classes |
|---|---:|---|
| `skos:definition` (no lang) | 4 | legal-rule-misstatement ×3, concept-mismatch ×1 |
| `skos:altLabel` (lang-tagged) | 8 | concept-substitution ×6, register ×1, untranslated ×1 |

The definition defects are substantive: *Motion to Stay Proceedings Pending Inter Partes Review*, *Trade Dress Infringement* (substitutes intent to deceive for likelihood of confusion, omits nonfunctionality), *Visitation of Grandparents* (states a categorical right that does not exist), *Actual Engagement Variables*. One `he-il` altLabel is flagged `register` — vulgar slang on *Oral Copulation*.

Each entry pins a `current_hash` for stale-write protection, and **no replacement values exist yet** — they are generated at run time by `scripts/run_confirmed_defect_corrections.py`, which has not been run against live providers.

Under the policy these are **12 × T2**: non-monotone, MAJOR bump, per-concept changelog. Their blast radius is 12 modified triples, 0 added, 0 removed — small in count, but they are the only staged rows that can make a downstream consumer's existing answer *wrong* rather than *incomplete*. They also cannot use escape valve 1: a wrong definition has no additive form.

The `register` and one `legal-rule-misstatement` entry arguably justify an out-of-cycle correction; that is a judgement call, and it is Damien's, not this document's.

### 5.3 `FOLIO.owl` ships 12 classes with an empty `skos:definition`

Not a staged change — a defect in the published file, found while classifying the digest:

`R40Dc9bD2Bbb0188bfa4C035` *Vratsa*, `R68A6f2AB34c8C619feCEe3e` *National Railroad Adjustment Board*, `R6C9da89DF079FC8fdc88f0d` *U.S. Office of Small Business Assistance*, `R6iOMiH_eTfClsEnn-_jWkA` *PA600 International Patent Prosecution*, `R8YtvLbmLTbuOrG1Ns7EfIw` *B200 Operations*, `RAyPCiRnrSpqlHX60SeZrLA` *PA500 International Patent Preparation*, `RBbe3FYj4RbGYHn9azrp82w` *B400 Bankruptcy-Related Advice*, `RDm4rfXgHt9wIDHbrUUGCGL` *Management*, `RODjSrfPzQr6SqM45eKmT7A` *B300 Claims and Plan*, `RRlxh-zpQQkqfqzHjz1913A` *PA200 Patent Investigation and Analysis*, `RnHqWL9K7RvKt0cOTLMx3pw` *B100 Administration*, `RqWEj2n_aQXyfLT5Z4KzCow` *TR200 Trademark Investigation and Analysis*.

Each has `<skos:definition></skos:definition>`. A consumer testing `if concept.definition:` sees "no definition"; one testing `if "definition" in concept:` sees "has a definition" and renders an empty string. Filling them is nominally T2 (a value exists) but observably T0 (the value carries no information). Recommendation: delete the empty triples as a T2 housekeeping item, which returns those 12 concepts to the honest T0 state, then fill them.

Note also that `RCaMM3whpuSnuFNtCOupTex` *Financial Sponsor* carries **two** `skos:definition` values, one of them the empty string — the only class in the file with a genuine competing-definitions problem.

---

## 6. Disposition

### Safe to ship today — no version boundary, no notice, T0

| Change | Count |
|---|---:|
| Digest KEEP — `skos:altLabel`, unambiguous after the change | 94,394 |
| Digest KEEP — `skos:example`, all slots empty | 14,830 |
| Agreements hidden labels, clean terms | 12 |
| Ontology header version metadata (`owl:versionIRI`, `versionInfo`, `priorVersion`, `dcterms:issued`, `dcterms:license`) | 5 |
| `dcterms:isReplacedBy` added to the 3 existing deprecated classes | 3 |
| **Total** | **109,244** |

_The first three rows (109,236) are staged changes and match the headline T0 count. The last two (8) are new recommendations from this analysis, not staged work._

Caveat, and it is not a small one: the 109,224 digest rows are safe *structurally*. They carry the digest's measured content-defect rate (30% on the 2026-07-28 sample basis, recomputed under ruling q2). Shipping them is a content decision, not a compatibility one — the policy says only that shipping them cannot break a consumer.

### Needs a collision decision before shipping — T1

| Change | Count |
|---|---:|
| Digest KEEP altLabels that make a surface form resolve to >1 concept | 6,136 |
| `Covenant`, `Indenture` on Agreements | 2 |

### Must be fixed, not shipped — invalid

| Change | Count |
|---|---:|
| `skos:hiddenLabel "Agreement"`, `"Contract"` — SKOS S13 disjointness violation | 2 |

### Needs a version boundary — T2 / T3-removal, MAJOR

| Change | Count |
|---|---:|
| `confirmed-defects.json` literal replacements | 12 |
| Tribal/language `subClassOf` removals (12 drops + 2 re-parent removals) | 14 |
| Empty-`skos:definition` housekeeping | 12 |
| *Financial Sponsor* competing definitions | 1 |

Of the tribal set, the 2 `Caddo` **additions** can ship early and additively under escape valve 1; only the 14 removals need the boundary.

### Needs a deprecation cycle

**Nothing.** No staged change removes or supersedes a concept.

### Blocked on content, not on policy

| Change | Count |
|---|---:|
| Digest REGENERATE — quarantined by gates G1–G6, values will change | 35,718 |
| Digest definitions (all 2,920) — ungrounded by construction | (included above) |

---

## Verdict

The change Damien was asked to approve is safe, and his instinct to stop was still correct — just not for the reason on the label. The 16 hidden labels merge additively, but 2 of them are invalid SKOS and 2 more silently re-point a surface form, and the branch carrying them is stale enough that one plausible way of applying it un-deprecates a deprecated class. Meanwhile the change that genuinely alters hierarchy (the 14 re-parentings) has a precisely bounded blast radius of 52 closure pairs, and the changes that can actually make a downstream answer *wrong* — the 12 confirmed content defects — were not in the frame at all.

The largest staged item by volume, the 115,360-row digest, turns out to be the structurally safest thing on the list: every row lands in an empty slot on an existing IRI, and 109,224 of them cannot be observed as a regression by any consumer. Its risk is entirely about whether the text is right.

## Caveat

Counts for the REGENERATE partition are provisional by construction — those rows exist to be replaced, so their tier cannot be assigned until the values are final. The 30% content-defect rate quoted for the digest is a recomputation from published tallies in `generative-folio/docs/evidence/2026-07-28-writeback-random-sample-audit.md`, not a re-adjudication; the row-level sample was not preserved. And the collision analysis in §2.2 and §4 uses case-folded, whitespace-normalised comparison within a language tag, which is the right model for a search index but is stricter than RDF term equality — under strict RDF semantics, fewer rows collide.
