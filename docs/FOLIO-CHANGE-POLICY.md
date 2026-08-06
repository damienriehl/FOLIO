# FOLIO change policy — classifying changes by blast radius

_Status: proposed. Written 2026-08-05 against `FOLIO.owl` at `e36f3f8` (18,327 `owl:Class` declarations). Every count in this document was computed from the file; the commands are in `docs/2026-08-05-staged-change-census.md`._

FOLIO is a published standard with implementers who did not ask permission before depending on it. This document exists to answer one question mechanically rather than by instinct: **given a proposed change, what can a consumer downstream observe, and what does that oblige us to do before shipping it?**

The organising principle is not severity-by-feel, and it is not monotonicity either. Monotonicity — the rule that adding axioms can only add entailments, never retract them — is a real and checkable property, and it appears throughout this document as a cross-check. But it cannot be the spine, for one disqualifying reason: **it cannot tell apart the two most different operations in this policy.** Deleting a class and reusing an IRI are both non-monotone, yet deleting is survivable (a dangling reference, noticed immediately) and reuse is categorically forbidden (every downstream record silently becomes wrong). A principle that ranks those the same is not the one to organise around.

Worse, it puts the two operations that share the *dangerous* signature at opposite ends. Adding a label that some other concept already answers to is perfectly monotone, and it silently changes which concept a resolver returns — the same class of harm as IRI reuse, arrived at by an "additive" change.

So the spine is two questions a maintainer can answer without running a reasoner:

1. **Can a consumer detect that something changed?** Loud failures — a 404, a validation error, a diff in a cached file — are survivable, because someone finds out. Silent ones are not.
2. **Does the change make a consumer's existing data _wrong_, or merely _incomplete_?** Incomplete data gets better on the next sync. Wrong data propagates.

|  | **Incomplete** | **Wrong** |
|---|---|---|
| **Loud** | changelog entry | version boundary + advance notice |
| **Silent** | mandatory pre-merge check | **forbidden** |

Every obligation in this document is derived from a change's cell in that grid. The cell is derived, in turn, from what the change touches and which direction it moves.

---

## 1. Classifying a change

A change is described by two things: **what it touches** and **which direction it moves**. Those two coordinates place it in the grid above, and the grid sets the obligation. Tiers are not a separate taxonomy to memorise — they are names for cells.

**What it touches**, from cheapest to most dangerous:

| | Layer | The thing at stake |
|---|---|---|
| **E** | **Existence** | whether a concept is in the ontology at all |
| **A** | **Annotation** | labels, definitions, notes — what a concept *says* |
| **H** | **Hierarchy** | `rdfs:subClassOf` and other axioms — what is *inferred* |
| **I** | **Identity** | which IRI denotes which concept |

**Which direction it moves:** **add**, **change**, or **remove**. Direction is not a footnote. Adding a parent and removing a parent are different operations with different blast radii, and so are adding a label and removing one; a policy that files each pair under a single heading will get the second one wrong.

The resulting cells, with the obligation each earns:

| Cell | Operation | Detectable? | Wrong or incomplete? | Obligation |
|---|---|---|---|---|
| **E-add** | mint a new concept | loud | incomplete → complete | changelog |
| **A-add** (free) | assert a label/definition where the slot is empty **and** the surface form resolves nowhere else | loud | incomplete | changelog |
| **A-add** (colliding) | assert a label a *different* concept already answers to | **silent** | incomplete, but a resolver may now answer **wrong** | **pre-merge collision check** |
| **A-change** | rewrite an existing definition or label | loud (content hash moves) | wrong, for anyone matching the old text | changelog naming subject, predicate, language tag, old-value hash |
| **A-remove** | delete a label or definition outright | **silent** for resolvers | a string that resolved now resolves to nothing | pre-merge check: who relies on this string? |
| **H-add** | add a `subClassOf` edge | silent to a cached closure | incomplete | changelog + advance notice |
| **H-remove** | remove a `subClassOf` edge | **silent** to a cached closure | **wrong** — materialised ancestor rows are now false | version boundary + notice + affected-pair count |
| **I-deprecate** | retire a concept via `owl:deprecated` | loud | incomplete | version boundary + notice (see §2) |
| **I-delete / I-rename** | remove or move an IRI | loud (404) | missing, not wrong | **do not** — deprecate instead (§2) |
| **I-reuse** | point an existing IRI at a different concept | **silent** | **wrong**, undetectably | **forbidden** (§2) |

Two cells deserve emphasis because they are counter-intuitive.

**A-add (colliding) is additive and still dangerous.** It adds triples, retracts nothing, and passes every monotonicity check — and it can still make a string→IRI resolver return a different concept than it did yesterday. FOLIO has already paid for this once: commit `e36f3f8` exists because the bare string `Agreement` resolved to *License (Agreement)* rather than *Agreements / Contracts*. That is why this cell earns a mandatory check rather than a changelog line.

**H-remove is the quietest destructive change we make.** Consumers materialise the transitive closure into their own databases, because closure queries are expensive. When an edge disappears, their stored rows do not error — they are simply false, and stay false until someone re-syncs. Nothing anywhere raises a signal.

### Cross-check: is it monotone?

For any change, ask whether it retracts an entailment. It is mechanically checkable and it catches mistakes the grid alone might not. But treat it as a **test, not a verdict** — `A-add (colliding)` is monotone and still requires a human decision, and `I-delete` and `I-reuse` are both non-monotone while sitting at opposite ends of acceptability.

### The tier is computed at merge, not at authoring

Whether an annotation addition is *free* or *colliding* depends on what the rest of the ontology contains — a global property, not a property of the diff. The same patch can be free today and colliding after an unrelated merge lands. **Classify at merge time, against the head you are merging into.** A tier assigned when a branch was cut is a stale claim, and this repository has already produced branches whose diffs mean something entirely different than they did when written (§7).

### Structural safety is not correctness

Every cell above answers "what can a consumer observe?" — and nothing more. A wrong definition dropped into an empty slot is `A-add (free)`: the safest cell on the board, breaking no consumer, and still misleading every human who reads it. **Blast radius and content quality are independent axes and must be judged independently.** The census that accompanies this policy shows them pointing in opposite directions on the very same rows: the change least likely to break anyone is drawn from the pool least likely to be right.


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

1. **Use `dcterms:isReplacedBy`, not `rdfs:seeAlso`.** `rdfs:seeAlso` asserts only that a resource is *related*; a consumer cannot mechanically conclude "migrate to this". `dcterms:isReplacedBy` says exactly that. `e36f3f8` used `rdfs:seeAlso`; all three currently-deprecated classes should be updated (itself an `A-add (free)` change — none of them has an `isReplacedBy` today).
2. **Overwriting the `skos:definition` with a deprecation notice is an `A-change` and destroys the record.** `RCiAtR0akBA7apMyfjy515B`'s original definition was replaced with the string "DEPRECATED: This concept is an editorial duplicate…". Put the notice in `rdfs:comment` and leave the definition intact, so a consumer looking up why their old data said what it said can still find out.
3. **Deprecated classes keep their parent edge, so they still appear in descendant queries.** That is the right trade-off — removing the edge would be an `H-remove` — but it means consumers must filter on `owl:deprecated`, and the policy must tell them so. State it in the release notes rather than assuming it.

**Merging two concepts** is done by deprecating one and pointing it at the other with `isReplacedBy` + `exactMatch`. Both IRIs remain resolvable forever. This is what "merge" must mean in FOLIO. It is an identity-level intent executed with annotation-level mechanics, and it is the only sanctioned form.

**Splitting one concept into two** mints new IRIs for the new senses and deprecates or narrows the original. It is the more disruptive direction and needs a release flagged `incompatibleWith`, because a consumer holding the old IRI cannot be told automatically which of the two new ones they meant.

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

It is also the easiest thing here to fix: the ontology node has no values for any of these predicates, so **adding them is `A-add (free)`** — the cheapest cell on the board. The remedy for "we cannot version safely" is itself the safest possible change.

### What it should declare

```xml
<owl:Ontology rdf:about="https://folio.openlegalstandard.org/">
    <owl:versionIRI rdf:resource="https://folio.openlegalstandard.org/2026-08-05/"/>
    <owl:versionInfo>2026-08-05T15:16:28Z</owl:versionInfo>
    <owl:priorVersion rdf:resource="https://folio.openlegalstandard.org/2026-08-04/"/>
    <owl:backwardCompatibleWith rdf:resource="https://folio.openlegalstandard.org/2026-08-04/"/>
    <dcterms:issued rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime"
        >2026-08-05T15:16:28Z</dcterms:issued>
    <dcterms:license rdf:resource="https://creativecommons.org/licenses/by/4.0/"/>
    <dc:title>FOLIO</dc:title>
    <dc:description>Federated Open Legal Information Ontology (FOLIO)</dc:description>
</owl:Ontology>
```

`owl:versionIRI` is the load-bearing one. It is the only version identifier with defined meaning in OWL: it names *this specific version* as distinct from the ontology IRI that names the series. It must resolve to an immutable copy of that exact file. Without a resolvable `versionIRI`, an implementer who wants to pin has nothing to pin *to* — which is precisely the position FOLIO's implementers are in today.

`owl:versionInfo` is a plain annotation with no defined structure; it carries the full ISO 8601 instant for humans and for tooling that does not parse the version IRI. `dcterms:issued` carries the same instant, typed `xsd:dateTime` so it sorts and compares mechanically. Publish `owl:priorVersion` so a consumer can walk the chain backwards.

### The identifier is a date, and dates carry no severity

**The version identifier is the release date, not a number.** `https://folio.openlegalstandard.org/2026-08-05/`.

This is deliberate. A number requires somebody to decide, on every release, whether the change was "major" — and that judgement drifts between maintainers, invites argument, and inflates. A date requires no judgement at all, and it does not pretend to say anything it does not know.

**Cadence: at most one release per day.** That makes the date a unique key, so the version IRI necessarily changes on every release with no bookkeeping. When a second release is genuinely needed on one date — a hotfix — it takes a suffix: `https://folio.openlegalstandard.org/2026-08-05-2/`. Use the suffix. **Never overwrite a version IRI that has already been published**, even hours later, even for an obvious mistake: an implementer may already have pinned it, and §2's rule applies to version IRIs exactly as it applies to concept IRIs.

Do not put a full timestamp with colons in the IRI path. It is legal, but awkward to dereference and inconsistent with the ordinary case. The instant lives in `versionInfo` and `dcterms:issued`, where it belongs.

### Severity: `owl:backwardCompatibleWith` and `owl:incompatibleWith`

Because the date says nothing about danger, the danger is stated separately — in OWL's own vocabulary, not an invention of ours. Every release asserts **exactly one** of these against its immediate prior version:

> **`owl:backwardCompatibleWith <prior>`** — everything the prior version entailed still holds. A consumer can upgrade without re-checking their own data.
>
> **`owl:incompatibleWith <prior>`** — something the prior version entailed no longer holds. A consumer must re-check.

This is the monotonicity cross-check from §1, doing real work: it is the mechanical test for which predicate to assert. Ask whether the new version retracts an entailment. If it does not, assert `backwardCompatibleWith`. If it does, assert `incompatibleWith`.

The mapping from §1's cells is one-to-one and requires no interpretation:

| §1 cell | Retracts an entailment? | Assert |
|---|:--:|---|
| `E-add` — mint a concept | no | `backwardCompatibleWith` |
| `A-add` (free or colliding) | no | `backwardCompatibleWith` |
| `H-add` — add a `subClassOf` edge | no | `backwardCompatibleWith` |
| `A-change` — rewrite a value | **yes** | **`incompatibleWith`** |
| `A-remove` — delete a value | **yes** | **`incompatibleWith`** |
| `H-remove` — remove an edge | **yes** | **`incompatibleWith`** |
| `I-deprecate` | no (the IRI still resolves) | `backwardCompatibleWith` |
| `I-delete` / `I-rename` / `I-reuse` | **yes** | forbidden — see §2 |

A release bundling several changes takes the **worst** cell in the bundle. One `A-change` in a batch of four thousand `A-add`s makes the whole release `incompatibleWith`, because a consumer cannot upgrade halfway.

**Note what this buys that a version number does not.** Under SemVer, correcting a wrong definition would be a MAJOR release — so a standard that honestly fixes its errors burns 2.0, 3.0, 4.0 in a month and tells its implementers nothing by the end. Here, the same correction ships on its own date and is flagged `incompatibleWith`. The signal is exact, it is machine-readable, and **there is no number to inflate**, so nothing pressures a maintainer into batching corrections purely to protect a version scheme. §5's argument for scheduling `A-change` work into windows survives on its own merits — giving implementers predictable windows — rather than as damage control.

**A caution on `A-add (colliding)`.** It asserts `backwardCompatibleWith`, and that is formally correct: no entailment is retracted. But §1 flags it as silently dangerous anyway, because it can re-point a resolver. **`backwardCompatibleWith` is a claim about entailment, not a promise that nothing downstream will behave differently.** That is exactly why the collision check is mandatory at merge, and why it cannot be discharged by pointing at this predicate.

---

## 4. The escape valve, and what it costs

A policy that forbids every non-additive change forever means FOLIO can never fix a modelling error, and FOLIO demonstrably has modelling errors — there are 12 confirmed content defects in `qa/ontology/confirmed-defects.json` right now, including definitions that misstate legal rules. So there must be a way through. There are three, in order of preference.

**1. Reshape the change into a lower tier.** Most `H-remove` re-parentings decompose into an additive half and a subtractive half. Adding the correct parent is monotone and ships immediately; removing the wrong parent waits for a release flagged `incompatibleWith`. In between, the concept has two parents — which in an ontology with 832 already-multi-parented classes is unremarkable — and every consumer sees the correct placement immediately while nobody's materialised closure goes stale.
*Cost:* the wrong edge stays visible for up to one release cycle, and anyone browsing the tree sees an oddity.
*Applies to:* the two Caddo re-parentings in the staged tribal fix. Does **not** apply to the twelve concepts whose entire fix *is* the removal.

**2. Deprecate rather than change.** Where a concept is wrong in a way that a rewrite cannot fix, mint a correct new concept and deprecate the old one per §2. Nothing is retracted; the old IRI keeps resolving; consumers migrate on their own schedule.
*Cost:* the ontology accumulates deprecated classes forever, and every consumer must learn to filter `owl:deprecated`. This is the cost every long-lived vocabulary pays, and it is the right one.

**3. Ship it, flagged.** When neither of the above works — a definition that is simply wrong, a subsumption edge that is simply false — ship the correction on its own dated release, assert `owl:incompatibleWith` against the prior version, and publish the machine-readable diff (§6) alongside it. Announce ahead of the date where the change is significant enough to warrant it.

**There is no quota and no scheduled window.** An earlier draft of this policy rationed breaking changes to two windows a year. That rule existed to protect a version *number* from inflation — a standard shipping 2.0, 3.0 and 4.0 in a month has told its implementers nothing — and this policy has no number to protect. Rationing corrections would buy nothing and cost accuracy, which is the wrong trade for a legal vocabulary: a definition that misstates a rule should not wait for a calendar slot.

What replaces the calendar is the flag. `owl:incompatibleWith` is machine-readable, so an implementer does not need to know FOLIO's release schedule to find out whether a release touches them — their tooling can ask. That is a stronger guarantee than a window, and it costs no one any correctness.

*Cost:* an implementer who upgrades blindly and ignores the flag can be surprised on any date. Mitigate by making the flag impossible to miss — in the ontology header, in the release notes, and in the diff — not by withholding the fix.

**What is never available:** IRI reuse. There is no window and no notice period that makes it safe, because the failure is undetectable by the consumer.

---

## 5. Protecting work in progress

This is the hardest case and the one that prompted the policy. An implementer mid-integration has pinned nothing (there is nothing to pin), may be mapping to labels rather than IRIs, may have a partially-reviewed mapping spreadsheet, and will not read a mailing list.

**1. Additive by default.** The single strongest protection, and the one that requires nothing from the implementer. An add-only release stream means a mid-integration consumer's work never becomes wrong — only incomplete. Everything else in this section is a mitigation for the cases where additive-only is not possible.

**2. Give them something to pin to.** Publish `owl:versionIRI` at an immutable URL (§3). Until that exists, "pin your version" is advice no one can follow. Publish a SHA-256 of each release artifact alongside it.

**3. Publish volatility; do not promise it.** An implementer wants to know which parts of FOLIO move often, so they can budget review effort. The tempting answer is to declare a slow-changing "core" and a fast periphery. **This policy deliberately does not.**

Two reasons. First, such a promise would restrain the *safest* operation there is: adding an upper-branch concept is `E-add`, it breaks nobody, and a slow-core commitment would make a maintainer hesitate over a change that cannot hurt anyone. Second, the boundary is not a stable set — "the concepts above the leaf level" moves every time the tree grows, so the promise could not be kept precisely even in good faith.

What replaces it is better, because it is a fact rather than a pledge: the per-release diffs of §6 let an implementer **measure** volatility across the concepts they actually use, instead of trusting a maintainer's forecast about concepts they may not. A promise about future behaviour that the maintainer is unsure of is worse than no promise at all — implementers plan against it.

**4. Deprecation is permanent, not a countdown.** A concept marked `owl:deprecated` **stays in the ontology and stays resolvable, indefinitely.** There is no window, no sunset, and no date after which it disappears — §2's permanence rule applies to deprecated concepts exactly as it applies to live ones. An earlier draft promised "at least one MAJOR version and no less than six months," which was a software-deprecation idiom imported without examining it: in software you eventually delete the deprecated symbol, and here we never do. A consumer who finds a deprecated concept does not need to know how long they have. They have as long as they like.

What they *do* need is the forwarding address, so every deprecated concept carries `dcterms:isReplacedBy` (§2) and a plain-language `rdfs:comment` explaining the retirement.

**4a. Deprecated concepts keep their parent edges — and that is a deliberate trade.** They therefore continue to appear in descendant queries, and **every consumer must filter on `owl:deprecated`**. The policy owes them that instruction prominently, in the release notes and in the README, because a consumer who does not filter will silently include retired concepts in their facets and counts.

The alternative — removing the parent edge at deprecation, so a retired concept is resolvable but unreachable by traversal — gives cleaner queries. It is rejected: removing an edge is `H-remove`, so it would make **every deprecation an incompatible release**, and cached closures would break each time. That would discourage the one mechanism that lets FOLIO retire a concept without ever breaking an IRI. A small permanent filtering tax on consumers is the better trade. **This was decided deliberately, not inherited** — the cheaper-looking option was examined and rejected because it would have penalised the mechanism that keeps IRIs permanent.

**5. A pre-release channel.** Publish the next release's `versionIRI` as a release candidate two to four weeks ahead of any release flagged `incompatibleWith`, plus the machine-readable diff (§6). A mid-integration consumer can diff their own concept set against it and find out whether the release touches them before it lands, which is exactly the question they cannot answer today.

**6. Label mappers are the exposed population — protect them specifically.** An implementer who mapped `"Agreement" → some IRI` is broken by `A-add (colliding)` and `A-change` changes that a IRI-based consumer never notices, and they are the majority of early integrations. Two obligations follow. First, the collision check in §1 is mandatory, not advisory. Second, the changelog must be keyed by surface form as well as by IRI, so a label mapper can search it for their own strings.

---

## 6. Machine-readable diffs

An implementer must be able to answer *"what changed for me?"* without diffing 18,327 classes. The answer is a per-release change log in JSONL, one row per changed triple, published beside the artifact:

```json
{"cell":"A-change","op":"replace","subject":"https://folio.openlegalstandard.org/R9WhMH4UyKR2iwelN1mU20r",
 "predicate":"http://www.w3.org/2004/02/skos/core#definition","language":null,
 "old_hash":"db94707e0348fd534d6c7fc222ea81b4c0550b88393cc29bc844443973f223e7",
 "new":"…","reason":"legal-rule-misstatement","release":"2026-08-05",
 "compatibility":"incompatibleWith"}
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

1. **Does it touch an IRI's identity?** Delete, rename, reuse, merge → `I-delete` / `I-rename` / `I-reuse`. **Stop.** Convert it to a deprecation per §2. Reuse is never available at any price.
2. **Does it remove or rewrite an existing triple?** → `A-change`, `A-remove`, or `H-remove`. The release asserts `owl:incompatibleWith`. Before accepting that, ask whether §4's escape valve 1 reshapes it into an addition — most re-parentings decompose into an additive half that ships today and a subtractive half that waits.
3. **Is it a new `rdfs:subClassOf`?** → `H-add`. Monotone, so `backwardCompatibleWith` — but record the change in descendant counts for the affected parents, because a consumer's materialised closure is now incomplete and nothing will tell them.
4. **Is it a new annotation?** Run both mechanical checks before classifying:
   - **S13 check:** does this subject already assert this exact literal (same lexical form, same language tag) under a different one of `skos:prefLabel` / `skos:altLabel` / `skos:hiddenLabel`? If yes, the change is **invalid SKOS** — fix it, do not ship it. This is not a cell in the grid; it is a defect.
   - **Collision check:** does `norm(value)` at this language tag already resolve to a *different* concept? If yes → `A-add (colliding)`, and a **human decides which concept owns the string**. If no, and the subject had no value for this predicate → `A-add (free)`.
5. **Is it a brand-new concept?** → `E-add`. The cheapest cell there is: nothing that already existed changes. Mint the IRI — it is permanent from that moment (§2).
6. **Judge the content separately, whatever the cell.** The grid measures disruption, never correctness. An `A-add (free)` can be entirely wrong and an `I-reuse` entirely well-intentioned. Never let a cheap cell substitute for review — the census shows the rows that are *safest structurally* are drawn from the pool that is *least grounded*.

7. **Verify against the merge result, never against the branch.** `git diff main..<branch>` on a stale branch reports the difference between two trees, which includes reverting everything `main` gained since the branch point. Use `git merge-tree --write-tree main <branch>` and diff *that*. This is not hypothetical: the staged hidden-label branch shows `25 insertions, 134 deletions` under `git diff` and `16 insertions, 0 deletions` as an actual merge, and anyone who resolved it by copying the branch's `FOLIO.owl` would have silently reverted all 10 `FOLIO.owl` commits `main` has gained since the branch point — including un-deprecating a deprecated class.

---

## Verdict

FOLIO's practice is already better than its documentation. It has never removed an IRI, it deprecates in place, and its QA pipeline already records changes in almost exactly the right shape. The gap is not discipline — it is that **the ontology declares no version**, so none of that discipline is legible to an implementer, and no deprecation window or pin instruction can even be expressed.

The first change to make under this policy is the one that makes the policy enforceable: add `owl:versionIRI`, `owl:versionInfo`, `owl:priorVersion`, `dcterms:issued` and `dcterms:license` to the ontology header, publish the versioned artifact at an immutable URL, and start emitting `changes-<version>.jsonl`. That is an `A-add (free)` change, it breaks nothing, and until it ships every other rule here is advisory.

## Caveat

A change's cell is computed from the file, not from the commit message. "Add synonyms" describes both an `A-add (free)` and an `A-add (colliding)` that quietly re-points a surface form at a different concept, and FOLIO's own history contains a commit titled `Add synonyms…` alongside one titled `Fix 'Agreement' precision bug` that removed a published `skos:altLabel`. Classify by diffing the triples.
