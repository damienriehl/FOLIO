# Using FOLIO

This guide is for consumers who want to inspect or reuse the ontology checked
into this repository. The examples report what the RDF represents; they do not
assert that a concept is legally correct for a particular application.

## Quick start

FOLIO's canonical input in this repository is [`FOLIO.owl`](../FOLIO.owl), an
RDF/XML file. With Python 3.12 and a cloned checkout:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r examples/requirements.txt
python examples/load_and_inspect.py
```

Dependency installation can require a package index. After RDFLib is installed,
all three examples read local files only: they need no credentials, provider
configuration, network connection, OWL import resolution, or write access to
the ontology.

Continue with the [runnable examples](../examples/README.md) and the
[ontology data model](ontology-model.md). Contributors creating identifiers
should follow the separate [IRI minting convention](../docs/solutions/conventions/minting-folio-concept-iris.md).

## Reusing a stable snapshot

Class IRIs are intended to remain stable, but labels, hierarchy, annotations,
and the checked-in snapshot can change. Pin a Git commit (and record its hash)
when reproducibility matters. The repository's
[change policy](../docs/FOLIO-CHANGE-POLICY.md) describes current obligations
and proposals; proposed versioned endpoints and release artifacts should not be
treated as facilities that already exist.

The ontology data is available under CC BY 4.0 and source code under MIT; see
the repository [license](../LICENSE) and [notices](../NOTICES.md).
