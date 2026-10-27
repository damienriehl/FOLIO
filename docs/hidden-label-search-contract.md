# Hidden-label search acceptance contract

This contract lets FOLIO and ontology consumers test the same Agreements aliases without treating producer RDF correctness as proof of viewer behavior.

## Shipped artifacts

- `qa/ontology/search/hidden-label-cases.json` is the independent, machine-readable expectation table. It identifies the source revision, stable concept IRIs, predicates, exact RDF literal metadata, producer expectations, and consumer result/display expectations.
- `qa/ontology/search/hidden-label-fixture.owl` is a minimal annotation projection of Agreements plus the Obligation and Indenture precision controls. It is test data, not a replacement ontology or an ontology release.
- `tests/test_hidden_label_search_contract.py` checks the table, fixture, both committed FOLIO OWLs, and the existing merge pipeline.

The six approved Agreements hidden labels are `Accord`, `Accords`, `Pact`, `Pacts`, `Compact`, and `Compacts`. `Pact` and `Compact` are the hidden-only sentinels. `Accords` is deliberately represented twice: an untagged hidden label and an independently asserted French (`fr-fr`) alternative label. Consumers must not collapse those RDF terms while importing them.

## Producer acceptance

From the repository root, run:

```bash
python -m pytest tests/test_hidden_label_search_contract.py -q
```

A pass establishes that the documented annotation projection occurs in the fixture, `FOLIO.owl`, and `FOLIO-webprotege-merge-output.owl`; that excluded aliases have not been attached to Agreements; and that the merge pipeline restores the hidden labels and reaches an idempotent second comparison. It does **not** establish that OntoKit imports or searches `skos:hiddenLabel`.

Plain RDF literals and `xsd:string` literals compare equivalently for this contract. Language-tagged literals remain distinct. Search-tokenization, stemming, fuzzy matching, and ranking are outside this contract.

## OntoKit consumer acceptance

Reinspect the current OntoKit checkout before implementation. The historical pointer was `ontokit-api/ontokit/services/ontology_index.py`, but this contract does not assume that path or its old `LABEL_PROPERTIES` behavior is current.

Use the real OntoKit import, index, query, and presentation paths—not a replacement matcher written only for this fixture—and record all of the following:

1. Import `hidden-label-fixture.owl` through the supported ontology import path and identify the index populated by that path.
2. Query every JSON case by its `query`. Each query must return its `target_iri` exactly once. Preserve the existing visible-label behavior and the display value in `consumer_expected.display_label`.
3. Establish hidden-label attribution with `agreements-hidden-pact` or `agreements-hidden-compact`. Prefer indexed predicate provenance. If the index does not expose provenance, repeat the same import and query with only that sentinel's hidden-label triple removed; the sentinel match must disappear while visible-label controls continue to pass. A result from broad full-text or fuzzy matching alone is insufficient.
4. Verify `agreements-hidden-accords` and `agreements-visible-accords-fr` independently. The hidden match must not promote `Accords` into the displayed concept name; the French alternative remains available under OntoKit's existing language/display policy.
5. Verify the Covenant and Indenture control cases retain their stated owners. Do not require fuzzy searches for those strings to return no other concepts.
6. Exercise both a fresh fixture import and the supported refresh/reindex procedure for an already imported ontology. Record which stored/indexed data was replaced or refreshed.
7. Add these assertions to OntoKit's normal automated suite and retain the case IDs in failure messages or parameter IDs.

Until a completed receipt exists, FOLIO producer verification is complete but downstream viewer acceptance remains pending under `foli-3`.

## Downstream work brief (not sent)

> Consume FOLIO's `qa/ontology/search/hidden-label-cases.json` and `hidden-label-fixture.owl` in OntoKit's existing import/search tests. Include `skos:hiddenLabel` in the real indexed search path, preserve visible-label display precedence and language identity, deduplicate results by concept IRI, and test both fresh import and refresh/reindex. Use `Pact` or `Compact` plus a paired fixture with that triple omitted to prove hidden-label attribution. Return the receipt below; do not mark FOLIO producer checks as consumer acceptance.

## Receipt template

Leave fields pending rather than inferring results.

```markdown
### Hidden-label consumer acceptance receipt

- FOLIO source revision:
- FOLIO corpus revision:
- OntoKit revision:
- Fresh-import path tested:
- Refresh/reindex path tested:
- Search/index implementation path:
- Display implementation path:
- Hidden-label attribution method and sentinel case ID:
- Test command(s) and result(s):
- Evidence/test file path(s):
- Result for all JSON case IDs:
- Known limitations or pending work:
```
