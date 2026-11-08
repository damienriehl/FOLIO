---
title: "fix: one phrase sense per place name in the OpenGloss mapping set (0.3.0)"
type: fix
status: rejected
date: 2026-11-08
origin: docs/plans/2026-11-08-2000-feat-opengloss-branch-aware-prior-plan.md (set 0.2.0)
---

# One phrase sense per place name (set 0.3.0)

## Problem

Set 0.2.0's weakest links sit on Location classes. The judged errors split in two:

- **Sibling senses:** OpenGloss often lists one place name with several senses: a city, a
  province, a river or an unrelated namesake. Method 0.2 emits the best phrase sense, and it also
  emits every other sense that scores at least 0.55 as an extra `closeMatch`. For a place name, those
  extras are mostly other referents. *Burgas*, *Gafsa*, *Dobrich*, *Offaly*, *Lazio* and *Southern*
  each have a correct sense 0 and wrong siblings.
- **Name-only homonyms:** some links rest on the name alone, with no word shared between the gloss
  and the class's definition or parents (*Pando*, *Paul*, *Nam Dinh*).

## Measurement (2026-11-08, gold set of 222 pairs, simulated on set 0.2.0)

| Rule | Links dropped | Judged among dropped (correct) | Judged precision | Gold recall |
|---|---:|---:|---:|---:|
| Baseline 0.2.0 | 0 | 0 (0) | 0.751 | 0.919 |
| A. Place classes keep only the best phrase sense | 225 | 8 (2) | 0.775 | 0.905 |
| B. A, plus drop modifier-word links with no non-name evidence | 599 | 11 (4) | 0.776 | 0.892 |
| C. A, plus drop every place link with no non-name evidence | 1,119 | 22 (8) | 0.805 | 0.865 |

## Decision

Adopt rule A. A place name denotes one place, so a class with the `place` profile emits only its
best-scoring phrase sense for each surface form. That sense still becomes `exactMatch` or
`closeMatch` under the existing rules, and word links are unchanged.

- **Why not B:** it adds almost nothing over A.
- **Why not C:** it buys precision by dropping correct links at a 36% rate.
- **Name-only homonyms:** they stay a known weakness, to fix with better evidence (a definition, a
  country match) rather than by deleting links.

The method becomes `opengloss-lexical/0.3` and the set becomes 0.3.0.

## Keep rule (decided before building)

- **Sample:** judge a random sample of 30 dropped links that are not already in the gold set, with
  the same rubric and judge type.
- **Keep 0.3.0** when at least 60% of the sampled dropped links are wrong, judged precision on the
  gold set rises, and gold recall falls by no more than 0.02.
- **Otherwise, revert:** keep 0.2.0 and record the result here.

## Units

- **U1:** in `matcher.py`, when a class's profiles include `place`, emit only the top-ranked phrase
  sense per surface form; the extra same-form senses are not emitted. Move `METHOD_VERSION` to
  `opengloss-lexical/0.3`. Tests:
  - **Place class:** a place class with three senses of its name gets exactly one phrase link.
  - **Legal class:** a legal-profile class keeps its sibling `closeMatch` links (unchanged from 0.2).
  - **Multi-branch:** a class in both Location and a legal branch counts as a place class.
  - **Determinism:** identical inputs give identical output.
- **U2:** bump the pins, regenerate, validate, diff against 0.2.0, judge the dropped sample, apply
  the keep rule, write the receipt, update the docs, review, PR, merge, and notify folio-resolve.

## Result (2026-11-08): rejected, set stays 0.2.0

The 0.3.0 build dropped 240 links, all `closeMatch`. On the gold set, judged precision rose from
0.751 to 0.784 and recall fell from 0.919 to 0.905, so both gold conditions passed.

The dropped-link condition failed. Of a random 30 dropped links, only 15 were wrong (50%, against
a 60% bar). Many dropped sibling senses were valid alternate referents of the same place: its city,
province or region sense (*Auckland*, *Ohio*, *Delhi*, *Otago*, *Bali*, *Lisboa*). The gold set's
eight dropped pairs had overstated the gain. The keep rule therefore reverted the change.

The 30 judgments joined `eval/gold.tsv`, since they judge links that 0.2.0 emits.

**Lesson:** for place names, a sibling sense is not evidence of error. A future fix needs evidence
that separates referents, such as matching the country or region in the class's parent labels
against the gloss, rather than a structural rule.
