# Runnable local examples

These Python 3.12 examples use RDFLib to read local RDF/XML. Install the small
consumer dependency set from the repository root:

```bash
python -m pip install -r examples/requirements.txt
```

Once installed, every command below runs offline and does not modify
`FOLIO.owl`. Pass a different local RDF/XML path where supported. URL inputs are
rejected rather than fetched.

## 1. Load and summarize

```bash
python examples/load_and_inspect.py
python examples/load_and_inspect.py path/to/local-copy.owl
```

`load_and_inspect.py` reports the triple count, the count of IRI subjects
explicitly declared as `owl:Class`, and a deterministic sample of at most ten
class IRIs. It does not count labeled properties or blank-node class
expressions as named classes.

## 2. Inspect labels and direct hierarchy

Supply the full IRI of an explicitly declared class:

```bash
python examples/labels_and_hierarchy.py \
  https://folio.openlegalstandard.org/RCzxVprwB3RwZ8EMewt18Jt
```

Use `--ontology path/to/local-copy.owl` for another local snapshot. Output
retains every supported label value and its RDF term kind, predicate, language,
and datatype. It reports only asserted immediate IRI-valued parents and
children; blank-node restrictions are not named parents. Deprecation values are
shown for the class and its neighbors. An empty deprecation list means no such
annotation was found, not that the resource is proven active.

An unknown IRI, a property IRI, or a relative identifier exits nonzero with an
error. A declared class without labels is valid and returns an empty label
list.

## 3. Query classes and direct children

```bash
python examples/query_classes.py
python examples/query_classes.py \
  --parent https://folio.openlegalstandard.org/RCzxVprwB3RwZ8EMewt18Jt
```

The fixed, read-only operation lists explicitly declared named classes, their
`rdfs:label` values, and deprecation annotations. `--parent` safely binds an IRI
and limits results to asserted direct children; in this snapshot the example
includes Co-Investment Fund
(`https://folio.openlegalstandard.org/R1cNH7TLMiSlSbIbdFsynUk`). An unmatched
parent succeeds with zero rows—it does not validate that the parent exists.

Output is deterministically ordered and limited to 20 solution rows. Multiple
labels can repeat a class, so 20 rows need not mean 20 classes, and truncation
can omit some labels. Use `labels_and_hierarchy.py` for complete inspection of
one concept. Declared classes without labels remain eligible.

For the RDF semantics behind these choices, read the
[ontology data model](../documentation/ontology-model.md).
