# FOLIO change policy — classifying changes by blast radius

_Status: proposed. Written 2026-08-05 against `FOLIO.owl` at `e36f3f8` (18,327 `owl:Class` declarations). Every count in this document was computed from the file; the commands are in `docs/2026-08-05-staged-change-census.md`._

FOLIO is a published standard with implementers who did not ask permission before depending on it. This document exists to answer one question mechanically rather than by instinct: **given a proposed change, what can a consumer downstream observe, and what does that oblige us to do before shipping it?**

The organising principle is not severity-by-feel. It is **monotonicity**. An RDFS/OWL knowledge base entails a set of facts; adding axioms can only ever add entailments, never retract them. So a change that only adds triples cannot make a previously-true answer false — it is *safe by construction*, whatever else is wrong with it. A change that removes or rewrites a triple can retract an entailment, and that is the real boundary a consumer feels. Everything below is a refinement of that single line.

---

## 1. The tiers

Five tiers, not four. The sketch this policy started from had one tier for "purely additive", but the census forced a split: adding a label into an empty slot and adding a label that some other concept already answers to are both "additive", and they are not remotely the same change. It also had no home for *removing* an annotation — which is not a hierarchy change and not an identity change, and which FOLIO has already shipped (see §6).

| Tier | Name | The operation | Monotone? |
|---|---|---|:--:|
| **T0** | **Fill** | Assert a triple where the subject had no value for that predicate, and the new surface form resolves to exactly one concept | yes |
| **T1** | **Enrich** | Assert a triple that joins existing values for the same subject+predicate, **or** that makes a surface form resolve to one more concept than before | yes |
| **T2** | **Revise** | Change or remove the value of an existing assertion (definition, label, note) | **no** |
| **T3** | **Restructure** | Add or remove `rdfs:subClassOf` / other axioms that change what is inferred | add: yes<br>remove: **no** |
| **T4** | **Reidentify** | Delete a class, change an IRI, merge two IRIs into one, or reuse an IRI for a different concept | **no** |

### T0 — Fill

**Operation.** `<C> <p> <v>` where `<C>` has no value of `<p>` (at that language tag), and `norm(v)` is not already a label of any other concept.

**What a consumer can observe.** A lookup that previously returned empty now returns a value. Nothing that previously returned a value returns a different one. No entailment is retracted. A consumer who has pinned nothing, cached everything, and mapped to labels rather than IRIs is *still* safe: every query they ran yesterday returns the same answer today, plus possibly more rows in a set-valued query.

**What it requires.** A changelog entry. Nothing else. No version boundary, no notice period, no deprecation. T0 is the tier FOLIO should default to, and the tier a maintainer should try hardest to reshape other changes into.

**The one caveat.** T0 is safe *structurally*; it says nothing about whether the content is correct. A wrong definition in a previously-empty slot harms readers even though it breaks no consumer. Groundedness and blast radius are independent axes and must be judged independently — the census shows them pointing in opposite directions on the same rows.

### T1 — Enrich

**Operation.** Either (a) a triple joining existing values on the same subject+predicate — a fourth `skos:altLabel` where three already exist — or (b) a triple whose surface form is already a label of some *other* concept.

**What a consumer can observe.** Set-valued queries return more rows. A consumer who wrote `labels[0]` or otherwise assumed cardinality one may now display or match a different string. Most importantly, in case (b), **a string→IRI resolver that returned exactly one concept now returns two**, and whichever tie-break it uses decides silently. That is the failure mode FOLIO has already had to fix once: commit `e36f3f8` exists because the bare string `Agreement` resolved to `License (Agreement)` rather than `Agreements / Contracts`.

**What it requires.** A changelog entry, and — for case (b) — a mandatory **collision check before merge**: does `norm(value)` at this language tag already resolve to a different concept? If yes, the change is not a label addition, it is a decision about which concept owns a surface form, and it needs a human to say so explicitly.

Adding a `skos:altLabel` or `skos:hiddenLabel` also entails the corresponding `rdfs:label` — SKOS Reference §5.2 condition **S12** makes all three sub-properties of `rdfs:label` — so a consumer reading `rdfs:label` sees enrichment even if they never touched SKOS.

**Validity, separately from tier.** SKOS Reference §5.2 condition **S13** declares `skos:prefLabel`, `skos:altLabel` and `skos:hiddenLabel` **pairwise disjoint**. Asserting the same literal (same lexical form, same language tag) on the same subject under two of them is not a low tier — it is invalid SKOS, and a validator will flag it. Check for this on every label addition; it is mechanical.

### T2 — Revise

**Operation.** Rewrite the value of an existing assertion, or delete an assertion without replacing it.

**What a consumer can observe.** The old string is gone. Concretely: a consumer matching on definition text breaks; a consumer displaying the definition shows different words, possibly in a document already reviewed by a lawyer; a content hash or ETag over the concept changes, invalidating caches; and in the deletion case, **a string→IRI mapping that used to resolve now returns nothing at all**. Deletion is the sharp edge of this tier and should be recorded as such — it is strictly more disruptive than a rewrite, because a rewrite leaves a value to find.

This is a delete plus an add. It is **not monotone**: an entailment that held yesterday does not hold today.

**What it requires.** A per-concept changelog entry naming the subject IRI, the predicate, the language tag, and a hash of the value being replaced. A **MINOR** version bump at minimum. Deletion of a label additionally requires the same collision check as T1 in reverse: who was relying on that string resolving?

### T3 — Restructure

**Operation.** Add or remove `rdfs:subClassOf` (or any axiom that changes inference).

**What a consumer can observe.** Ancestor and descendant queries change. A consumer who materialised the transitive closure into their own database — the normal thing to do, because closure queries are expensive — now holds stale rows and will not notice, because nothing errors. A consumer running a reasoner gets a different classification. A faceted search filtered on a top-level branch gains or loses members.

**Adding an edge is monotone; removing one is not.** This distinction is operationally load-bearing and is the escape valve described in §4: a re-parenting can usually be *split* into an additive half that ships immediately and a subtractive half that waits for a version boundary. FOLIO already has 832 classes with more than one asserted parent, so a temporary second parent is not an anomaly in this ontology — it is the existing idiom.

**What it requires.** Additive-only: changelog + MINOR. Any removal: changelog naming every affected subject **and** the count of ancestor/descendant pairs that disappear, plus a **MAJOR** version bump.

### T4 — Reidentify

**Operation.** Delete a class; change an IRI; merge two IRIs; reuse an IRI for a different concept.

**What a consumer can observe.** For deletion and IRI change: a stored IRI in a customer's own database becomes a dangling reference, and dereferencing the IRI 404s. That fails loudly, which is bad but survivable.

**IRI reuse fails silently, and is categorically worse than deletion.** If `R88D8i8AcSTUig2X3yPbFHg` means *Agreements* today and something else next year, every downstream record tagged with that IRI is now *wrong* rather than *missing*, and no error is raised anywhere. There is no mechanism by which a consumer can detect this. This is the one operation in the whole policy that is simply forbidden — see §2.

**What it requires.** See §2. In practice: don't. Use the deprecation pattern instead.

---

## 2. IRI permanence

**The rule.** A FOLIO IRI, once published, is never deleted and never reused. It resolves forever, to the same concept, or to a deprecated marker for that concept. There is no exception, including for concepts created in error.

**FOLIO already obeys this rule; it has simply never written it down.** Across the entire published history of `FOLIO.owl` — 18 commits touching the file, from `c93525c` to `e36f3f8` — the count of class IRIs removed is **zero**. The file has gone 18,324 → 18,327 classes, monotonically. So this section codifies existing practice rather than imposing a new constraint.

FOLIO also already has the correct pattern in the file, applied by hand in `e36f3f8` to the editorial duplicate `RCiAtR0akBA7apMyfjy515B`. Formalised, and with the annotation corrected:

```xml
<owl:Class rdf:about="https://folio.openlegalstandard.org/RCiAtR0akBA7apMyfjy515B">
    <!-- 1. keep the class declaration and its parent, so the IRI still resolves
            and the concept is still reachable from the tree -->
    <rdfs:subClassOf rdf:resource="https://folio.openlegalstandard.org/R8H8cpx25KBk3kH55YwSdDv"/>

    <!-- 2. mark it deprecated -->
    <owl:deprecated rdf:datatype="http://www.w3.org/2001/XMLSchema#boolean">true</owl:deprecated>

    <!-- 3. say what to use instead, MACHINE-READABLY.
            dcterms:isReplacedBy is the correct predicate; rdfs:seeAlso is not,
            because seeAlso means "related", which no consumer can act on. -->
    <dcterms:isReplacedBy rdf:resource="https://folio.openlegalstandard.org/RKKRGOkIme6pnG2BSePt1Z"/>

    <!-- 4. skos:exactMatch ONLY when the two concepts genuinely denote the same
            thing, as here (an editorial duplicate). Omit it for a supersession
            that narrows or splits the meaning. -->
    <skos:exactMatch rdf:resource="https://folio.openlegalstandard.org/RKKRGOkIme6pnG2BSePt1Z"/>

    <!-- 5. human-readable, and mark the label so a viewer shows the state -->
    <rdfs:label>DEPRECATED Duplicate of License (Agreement)</rdfs:label>
    <rdfs:comment>DEPRECATED as of 2.1.0. Editorial duplicate of License (Agreement).
        Use https://folio.openlegalstandard.org/RKKRGOkIme6pnG2BSePt1Z instead.</rdfs:comment>
</owl:Class>
```

Three corrections to the pattern as currently applied in `FOLIO.owl`:

1. **Use `dcterms:isReplacedBy`, not `rdfs:seeAlso`.** `rdfs:seeAlso` asserts only that a resource is *related*; a consumer cannot mechanically conclude "migrate to this". `dcterms:isReplacedBy` says exactly that. `e36f3f8` used `rdfs:seeAlso`; all three currently-deprecated classes should be updated (itself a T0 change — none of them has an `isReplacedBy` today).
2. **Overwriting the `skos:definition` with a deprecation notice is a T2 change and destroys the record.** `RCiAtR0akBA7apMyfjy515B`'s original definition was replaced with the string "DEPRECATED: This concept is an editorial duplicate…". Put the notice in `rdfs:comment` and leave the definition intact, so a consumer looking up why their old data said what it said can still find out.
3. **Deprecated classes keep their parent edge, so they still appear in descendant queries.** That is the right trade-off — removing the edge would be a T3 removal — but it means consumers must filter on `owl:deprecated`, and the policy must tell them so. State it in the release notes rather than assuming it.

**Merging two concepts** is done by deprecating one and pointing it at the other with `isReplacedBy` + `exactMatch`. Both IRIs remain resolvable forever. This is what "merge" must mean in FOLIO. It is a T4-intent change executed with T2 mechanics, and it is the only sanctioned form.

**Splitting one concept into two** mints new IRIs for the new senses and deprecates or narrows the original. It is the more disruptive direction and needs a MAJOR boundary, because a consumer holding the old IRI cannot be told automatically which of the two new ones they meant.

---

## 3. Versioning

### What FOLIO declares today

Nothing. The entire ontology header is:

```xml
<owl:Ontology rdf:about="https://folio.openlegalstandard.org/">
    <dc:description>Federated Open Legal Information Ontology (FOLIO)</dc:description>
    <dc:title>FOLIO</dc:title>
</owl:Ontology>
```

There is no `owl:versionIRI`, no `owl:versionInfo`, no `dcterms:issued`, no `owl:priorVersion`, no `dcterms:license`. **This is inadequate, and it is the root cause of the problem this policy addresses.** An implementer today cannot pin a version, cannot detect that a version changed, cannot tell two downloads apart except by hashing 18 MB of XML, and cannot be given a deprecation window because there is no unit in which to express one. Every other rule in this document is unenforceable until this is fixed.

It is also the easiest thing here to fix: the ontology node has no values for any of these predicates, so **adding them is a T0 change**. The remedy for "we cannot version safely" is itself the safest possible change.

### What it should declare

```xml
<owl:Ontology rdf:about="https://folio.openlegalstandard.org/">
    <owl:versionIRI rdf:resource="https://folio.openlegalstandard.org/2.1.0/"/>
    <owl:versionInfo>2.1.0</owl:versionInfo>
    <owl:priorVersion rdf:resource="https://folio.openlegalstandard.org/2.0.0/"/>
    <dcterms:issued rdf:datatype="http://www.w3.org/2001/XMLSchema#date">2026-08-05</dcterms:issued>
    <dcterms:license rdf:resource="https://creativecommons.org/licenses/by/4.0/"/>
    <dc:title>FOLIO</dc:title>
    <dc:description>Federated Open Legal Information Ontology (FOLIO)</dc:description>
</owl:Ontology>
```

`owl:versionIRI` is the load-bearing one. It is the only version identifier with defined meaning in OWL: it names *this specific version* as distinct from the ontology IRI that names the series. It must resolve to an immutable copy of that exact file. Without a resolvable `versionIRI`, an implementer who wants to pin has nothing to pin *to* — which is precisely the position FOLIO's implementers are in today.

`owl:versionInfo` is a plain annotation with no defined structure; it is for humans and for tooling that does not parse the versionIRI. `dcterms:issued` gives the date. Publish `owl:priorVersion` so a consumer can walk backwards.

### What the number means

Not software SemVer — an ontology has no function signatures to break. But the same three-part shape works if each position is anchored to something real, and here the anchor is monotonicity:

> **MAJOR** — the new version does not entail everything the old version entailed.
> **MINOR** — everything the old version entailed still holds; new content was added.
> **PATCH** — no change to any assertion about a concept (build metadata, serialisation, header).

That criterion is mechanically checkable, not a judgement call, and it maps onto the tiers exactly:

| Tier | Monotone | Bump |
|---|:--:|---|
| T0 Fill | yes | MINOR |
| T1 Enrich | yes | MINOR |
| T2 Revise | no | **MAJOR** |
| T3 Restructure — additions only | yes | MINOR |
| T3 Restructure — any removal | no | **MAJOR** |
| T4 Reidentify | no | **MAJOR** |

The uncomfortable consequence, stated plainly: **fixing a wrong definition is a MAJOR release.** That is correct and it is the honest cost of publishing text that other people rely on verbatim. It is also why §5 recommends batching T2 work into scheduled windows rather than shipping corrections one at a time — a standard that ships 2.0, 3.0, 4.0 in a month has told its implementers nothing.

---

## 4. The escape valve, and what it costs

A policy that forbids T2+ forever means FOLIO can never fix a modelling error, and FOLIO demonstrably has modelling errors — there are 12 confirmed content defects in `qa/ontology/confirmed-defects.json` right now, including definitions that misstate legal rules. So there must be a way through. There are three, in order of preference.

**1. Reshape the change into a lower tier.** Most T3 re-parentings decompose into an additive half and a subtractive half. Adding the correct parent is monotone and ships immediately; removing the wrong parent waits for the next MAJOR. In between, the concept has two parents — which in an ontology with 832 already-multi-parented classes is unremarkable — and every consumer sees the correct placement immediately while nobody's materialised closure goes stale.
*Cost:* the wrong edge stays visible for up to one release cycle, and anyone browsing the tree sees an oddity.
*Applies to:* the two Caddo re-parentings in the staged tribal fix. Does **not** apply to the twelve concepts whose entire fix *is* the removal.

**2. Deprecate rather than change.** Where a concept is wrong in a way that a rewrite cannot fix, mint a correct new concept and deprecate the old one per §2. Nothing is retracted; the old IRI keeps resolving; consumers migrate on their own schedule.
*Cost:* the ontology accumulates deprecated classes forever, and every consumer must learn to filter `owl:deprecated`. This is the cost every long-lived vocabulary pays, and it is the right one.

**3. Ship the T2/T3-removal at a scheduled MAJOR boundary.** When neither of the above works — a definition that is simply wrong, a subsumption edge that is simply false — batch it, announce it, and ship it at a published date.
*Cost:* correctness waits for the calendar. Mitigate by holding at most two MAJOR windows a year and publishing the queue of pending corrections in between, so an implementer can see a fix coming and act early. A known-wrong definition sitting in a queue with a ship date is a better failure than a silent rewrite.

**What is never available:** IRI reuse. There is no window and no notice period that makes it safe, because the failure is undetectable by the consumer.

---

## 5. Protecting work in progress

This is the hardest case and the one that prompted the policy. An implementer mid-integration has pinned nothing (there is nothing to pin), may be mapping to labels rather than IRIs, may have a partially-reviewed mapping spreadsheet, and will not read a mailing list.

**1. Additive by default.** The single strongest protection, and the one that requires nothing from the implementer. A T0/T1-only release stream means a mid-integration consumer's work never becomes wrong — only incomplete. Everything else in this section is a mitigation for the cases where additive-only is not possible.

**2. Give them something to pin to.** Publish `owl:versionIRI` at an immutable URL (§3). Until that exists, "pin your version" is advice no one can follow. Publish a SHA-256 of each release artifact alongside it.

**3. A slow core and a fast periphery.** The concepts an implementer maps first — the upper branches, the ~2,800 concepts above the leaf level — should change on a slower cadence than the long tail of jurisdiction-specific leaves. Declare which is which. A consumer integrating against *Agreements / Contracts* or *Actor / Player* needs different guarantees than one consuming individual tribal-government entries, and telling them so lets them budget their review effort.

**4. Published deprecation windows.** A concept marked `owl:deprecated` remains present and resolvable for **at least one MAJOR version and no less than six months**, whichever is longer. State the window in the release notes and in the `rdfs:comment`, so a consumer who finds a deprecated concept knows how long they have.

**5. A pre-release channel.** Publish the next release's `versionIRI` as a release candidate two to four weeks ahead of a MAJOR, plus the machine-readable diff (§6). A mid-integration consumer can diff their own concept set against it and find out whether the release touches them before it lands, which is exactly the question they cannot answer today.

**6. Label mappers are the exposed population — protect them specifically.** An implementer who mapped `"Agreement" → some IRI` is broken by T1 and T2 changes that a IRI-based consumer never notices, and they are the majority of early integrations. Two obligations follow. First, the collision check in §1 is mandatory, not advisory. Second, the changelog must be keyed by surface form as well as by IRI, so a label mapper can search it for their own strings.

---

## 6. Machine-readable diffs

An implementer must be able to answer *"what changed for me?"* without diffing 18,327 classes. The answer is a per-release change log in JSONL, one row per changed triple, published beside the artifact:

```json
{"tier":"T2","op":"replace","subject":"https://folio.openlegalstandard.org/R9WhMH4UyKR2iwelN1mU20r",
 "predicate":"http://www.w3.org/2004/02/skos/core#definition","language":null,
 "old_hash":"db94707e0348fd534d6c7fc222ea81b4c0550b88393cc29bc844443973f223e7",
 "new":"…","reason":"legal-rule-misstatement","release":"2.1.0"}
```

`op` is one of `add` / `remove` / `replace`. `old_hash` is a SHA-256 of the exact literal being replaced or removed, which lets a consumer verify they held the version being described rather than some other one. With this file an implementer filters by their own IRI set — or greps it for their own label strings — and gets a complete, exact answer in seconds.

**FOLIO has already invented this record format and simply has not published it.** `qa/ontology/confirmed-defects.json` carries `subject`, `predicate`, `language`, `datatype`, `current_hash`, and a `defect_class` — which is the schema above, minus `tier` and `op`, used as an inbound work ledger rather than an outbound change record. Emitting the release diff is largely a matter of writing out what that pipeline already knows.

Publish alongside each release:

- `changes-<version>.jsonl` — every changed triple, as above.
- `deprecations.jsonl` — cumulative, not per-release: every deprecated IRI, its replacement, the version it was deprecated in, and the earliest version it may be removed in (which, per §2, is never — but the field documents that).
- `SHA256SUMS` — for the ontology artifact and both JSONL files.

---

## 7. Applying the policy — the maintainer's checklist

For any proposed change, in order:

1. **Does it touch an IRI's identity?** Delete, rename, reuse, merge → **T4**. Stop; convert to a deprecation per §2.
2. **Does it remove or rewrite any existing triple?** → **T2** (annotation) or **T3-removal** (axiom). MAJOR bump. Ask first whether §4's escape valve 1 reshapes it into an addition.
3. **Is it a new `rdfs:subClassOf`?** → **T3-addition**. Monotone. MINOR. Record the change in descendant counts for the affected parents.
4. **Is it a new annotation?** Then run both mechanical checks before assigning a tier:
   - **S13 check:** does the same subject already assert this exact literal (same lexical form, same language tag) under a different one of `skos:prefLabel` / `skos:altLabel` / `skos:hiddenLabel`? If yes, the change is **invalid SKOS** — fix it, do not ship it.
   - **Collision check:** does `norm(value)` at this language tag already resolve to a *different* concept? If yes → **T1**, and a human decides which concept owns the string. If no, and the subject had no value for this predicate → **T0**.
5. **Regardless of tier, judge the content separately.** Tier measures disruption, not correctness. A T0 change can be entirely wrong and a T4 change entirely right. Never let a low tier substitute for review — see the census, where the *safest* rows structurally are the *least* grounded ones.
6. **Verify against the merge result, never against the branch.** `git diff main..<branch>` on a stale branch reports the difference between two trees, which includes reverting everything `main` gained since the branch point. Use `git merge-tree --write-tree main <branch>` and diff *that*. This is not hypothetical: the staged hidden-label branch shows `25 insertions, 134 deletions` under `git diff` and `16 insertions, 0 deletions` as an actual merge, and anyone who resolved it by copying the branch's `FOLIO.owl` would have silently reverted all 10 `FOLIO.owl` commits `main` has gained since the branch point — including un-deprecating a deprecated class.

---

## Verdict

FOLIO's practice is already better than its documentation. It has never removed an IRI, it deprecates in place, and its QA pipeline already records changes in almost exactly the right shape. The gap is not discipline — it is that **the ontology declares no version**, so none of that discipline is legible to an implementer, and no deprecation window or pin instruction can even be expressed.

The first change to make under this policy is the one that makes the policy enforceable: add `owl:versionIRI`, `owl:versionInfo`, `owl:priorVersion`, `dcterms:issued` and `dcterms:license` to the ontology header, publish the versioned artifact at an immutable URL, and start emitting `changes-<version>.jsonl`. That is a T0 change, it breaks nothing, and until it ships every other rule here is advisory.

## Caveat

The tier of a change is computed from the file, not from the commit message. "Add synonyms" describes both a T0 change and a T1 change that quietly re-points a surface form at a different concept, and FOLIO's own history contains a commit titled `Add synonyms…` alongside one titled `Fix 'Agreement' precision bug` that removed a published `skos:altLabel`. Classify by diffing the triples.
