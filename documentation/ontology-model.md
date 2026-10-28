# FOLIO ontology data model

## Identifiers and subjects

FOLIO concepts use permanent, opaque IRIs. Do not infer meaning from the final
IRI segment or replace a known IRI with one made from a label. Named concepts
used by these examples are IRI subjects explicitly declared `owl:Class`.
Properties are different RDF subjects even when they have labels, and anonymous
class expressions are blank nodes rather than named concepts.

## Labels are RDF values

A class can have zero, one, or many values for `rdfs:label`, `skos:prefLabel`,
`skos:altLabel`, and `skos:hiddenLabel`. Each value retains its predicate,
lexical text, language tag, and datatype. Language tags such as `en` and
`en-US` are distinct. Consumers should choose their own display-language and
fallback policy; a hidden label is not automatically a display name.

The inspection example also exposes a non-literal label object instead of
silently presenting it as text. This preserves the distinction between RDF
terms and makes unusual source data visible.

## Asserted direct hierarchy

An IRI-valued `rdfs:subClassOf` object is an asserted direct parent. The inverse
edge identifies a direct child. The examples do not compute transitive
ancestors, run an OWL reasoner, or claim that absence of an edge proves concepts
are unrelated.

`rdfs:subClassOf` can also point to a blank-node OWL restriction or another
anonymous class expression. Such a node encodes a constraint; it is not a
named parent and is intentionally excluded from the direct named-parent list.

## Deprecation and provenance

`owl:deprecated` values are annotations represented in the data. A missing
annotation is reported as an empty list, not converted to `false` and not
treated as proof that a concept is active. Deprecated classes and their edges
remain inspectable. Applications may impose their own active-only policy.

Results come from the exact local snapshot supplied to a command. They are not
live API responses and include no inferred meaning. Record the Git commit and
the input file hash when results must be reproducible; see
[Using FOLIO](README.md#reusing-a-stable-snapshot).
