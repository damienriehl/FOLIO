# Audit of already-published FOLIO.owl — 2026-07-29

Seeded audit (`random.seed(20260729)`) of content **already live** in the published
standard, run because a sister audit of the *unwritten* generative-folio digest
found a 32% defect rate and a template inventing federal tribal recognition. The
question was whether the same problem had already shipped.

## Headline: the feared problem is NOT here, but a different one is

**The tribal-recognition template has not shipped.** Zero live definitions contain
`federally recognized`, `federally or state-recognized`, `under applicable federal
and state law`, `exercises governmental authority`, or `tribal lands`. The single
`self-governance` hit is *Free State* (a South African province), which is correct.

**Provenance correction — the live annotations are not from the generative-folio
pipeline at all.** They were present in `c16f652`, the initial SOLI commit
(2024-08-23), which already contained 15,659 definitions / 2,865 examples / 52,230
lang-tagged altLabels. The later `c93525c` "rebrand" (2025-03-13) only renamed SOLI
to FOLIO and rewrote IRIs and prefixes — it did not generate the corpus. Any earlier
statement attributing this content to the rebrand import is wrong.

## Live defect rates

| Component | Clear defects | Rate |
|---|---:|---:|
| Definitions | 4/40 | 10.0% |
| Examples | 0/30 | 0.0% |
| Lang-tagged altLabels | 8/30 | 26.7% |

Only clear factual, legal, grounding, or language failures were counted; merely terse
or awkward text was not.

## Defects worth correcting, ranked

### 1. Legal-rule misstatements in live definitions

| Concept | IRI | Problem |
|---|---|---|
| Motion to Stay Pending Inter Partes Review | `R9WhMH4UyKR2iwelN1mU20r` | Says "a third party reviews the validity". A third party *petitions*; the PTAB conducts the review and decides patentability. |
| Trade Dress Infringement | `R5IK3HbwB8GonR7f8MQYZ3` | Substitutes actual intent "to deceive" for the likelihood-of-confusion standard; omits nonfunctionality (15 U.S.C. § 1125). |
| Visitation of Grandparents | `RDspheq1ywN6ph6VaPCXXLq` | Asserts a categorical "legal right" of grandparent visitation. *Troxel v. Granville* rejects that framing; any remedy is jurisdiction-dependent and constrained by a fit parent's rights. |
| Actual Engagement Variables | `RBDulWh05GQyLEJ6hwbt0mg` | "The amount of true fees/costs" — describes one amount, not variables; does not define the named concept. |

### 2. Wrong legal translations (live)

| Concept | IRI | Locale | Problem |
|---|---|---|---|
| Maintenance and Cure | `RBBqzbaCc2sDtwMhCHYXUi` | ja-jp | メンテナンスと治療 — "maintenance and medical treatment"; loses the maritime doctrine entirely. |
| Discharge in Bankruptcy | `R8bI7utrpB2lXtuUuLqUWqa` | hi-in | रिहाई = release/liberation, not legal discharge of debts. |
| Motion to Dismiss for Lack of Standing | `R1SN9oCHEx4gLQaVfkobvw` | he-il | Renders "motion" as תביעה (lawsuit) — reads "a lawsuit to dismiss the lawsuit". |
| Motion for Relief Because No Longer Equitable | `R9nncQII5NePGstKEVGQrKr` | he-il | Same motion/lawsuit error, plus the equitable standard rendered colloquially. |
| Co-Party Coordination | `RBBu1oEeGLOZwYrYMPTvgfz` | he-il | "party" became מפלגה — a *political* party. |

### 3. Register and language failures (live)

| Concept | IRI | Locale | Problem |
|---|---|---|---|
| Oral Copulation | `RBqBxJEzhWW5x12JraZHgQd` | he-il | Vulgar slang rather than neutral legal register. **Fix first** — it is the most publicly embarrassing item in the file. |
| Nyoro | `R9TsmV9GF0oB9X0KbWAOnOd` | zh-cn | Unchanged Latin-script copy, not a translation. |
| Counterfeiting | `R9Zpw6W6vllQC97Xj87kMAX` | hi-in | नकली is the adjective "fake", not the offense. |

### 4. Redundant localization — en-gb is 89.6% noise

**5,477 of 52,238 (10.5%)** lang-tagged altLabels are byte-identical to their
concept's `rdfs:label`. It is overwhelmingly one locale:

| Tag | Duplicates / total |
|---|---:|
| `en-gb` | **4,488 / 5,008 — 89.6%** |
| de-de | 332 / 5,450 |
| fr-fr | 255 / 5,450 |
| pt-br | 235 / 5,450 |
| zh-cn | 46 / 5,450 |
| ja-jp | 43 / 5,450 |
| es-mx / es-es | 35 / 4,970 · 33 / 4,969 |
| he-il | 8 / 4,994 |
| hi-in | 1 / 4,988 |

The digest's en-gb duplication problem is therefore **already live, and worse**.
These inflate apparent localization coverage while carrying no information.

## Verdict

**Correct, do not retract.** The examples sample was clean, the tribal-recognition
scan was clean, and the definition defect rate (10%) does not justify pulling the
corpus. What it justifies is targeted correction of the items above plus a wider
translation review — the 26.7% translation rate is the real signal, and it is a
pre-existing SOLI-era issue rather than anything the current pipeline introduced.

## Caveat

The Codex worker could not reach `generative-folio/docs/writeback/digest-0001/payload/`
(outside its workspace root), so a direct wording comparison between live content and
the proposed digest was not performed. The generator-sharing question is answered from
git history instead — different origin, different era — but not from text comparison.
