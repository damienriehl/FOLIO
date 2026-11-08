"""Read FOLIO RDF/XML without constructing an RDF graph."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET

NS = {
    'owl': 'http://www.w3.org/2002/07/owl#',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
    'skos': 'http://www.w3.org/2004/02/skos/core#',
}
LANG = '{http://www.w3.org/XML/1998/namespace}lang'
ABOUT = f"{{{NS['rdf']}}}about"
RESOURCE = f"{{{NS['rdf']}}}resource"
FIELDS = ('rdfs:label', 'skos:prefLabel', 'skos:altLabel')
ENGLISH = frozenset(('', 'en', 'en-us', 'en-gb'))
FOLIO_PREFIX = 'https://folio.openlegalstandard.org/'


@dataclass(frozen=True)
class FolioClass:
    iri: str
    labels: tuple[tuple[str, str], ...]
    definitions: tuple[str, ...] = ()
    parents: tuple[str, ...] = ()
    parent_labels: tuple[str, ...] = ()
    branches: tuple[str, ...] = ()

    @property
    def subject_id(self) -> str:
        return 'FOLIO:' + self.iri[len(FOLIO_PREFIX):] if self.iri.startswith(FOLIO_PREFIX) else self.iri

    @property
    def label(self) -> str:
        return next((value for field in FIELDS for value, source in self.labels if source == field), '')


def normalize(text: str) -> str:
    """NFKC, casefold, remove one trailing qualifier, then fold separators."""
    text = unicodedata.normalize('NFKC', text).casefold().strip()
    text = re.sub(r'\s*\([^()]*\)\s*$', '', text)
    return ' '.join(re.sub(r'[-/_]', ' ', text).split())


def surface_forms(cls: FolioClass) -> tuple[tuple[str, str], ...]:
    forms = set()
    for label, field in cls.labels:
        for value in [label, *re.split(r'\s*/\s*', label)]:
            form = re.sub(r'^\W+|\W+$', '', normalize(value))
            if form:
                forms.add((form, field))
    return tuple(sorted(forms))


def load_folio(path: str | Path) -> list[FolioClass]:
    records = {}
    for node in ET.parse(path).getroot().iter(f"{{{NS['owl']}}}Class"):
        iri = node.get(ABOUT)
        if not iri or any((d.text or '').strip().casefold() in ('true', '1') for d in node.findall('owl:deprecated', NS)):
            continue
        labels = []
        for field in FIELDS:
            for child in node.findall(field, NS):
                if child.get(LANG, '').casefold() in ENGLISH and child.text:
                    labels.append((child.text, field))
        definitions = tuple(sorted({
            d.text for d in node.findall('skos:definition', NS)
            if d.text and d.get(LANG, '').casefold() in ENGLISH
        }))
        parents = tuple(sorted({
            p.get(RESOURCE) for p in node.findall('rdfs:subClassOf', NS)
            if p.get(RESOURCE)
        }))
        records[iri] = FolioClass(iri, tuple(sorted(set(labels))), definitions, parents)
    branch_cache: dict[str, frozenset[str]] = {}
    thing = NS['owl'] + 'Thing'

    def walk_branches(iri: str, visiting: set[str]) -> tuple[frozenset[str], bool]:
        if iri in branch_cache:
            return branch_cache[iri], False
        if iri in visiting:
            return frozenset(), True
        if iri not in records or iri == thing:
            return frozenset(), False
        visiting.add(iri)
        cls = records[iri]
        branches = {iri} if thing in cls.parents else set()
        cyclic = False
        for parent in cls.parents:
            inherited, parent_cyclic = walk_branches(parent, visiting)
            branches.update(inherited)
            cyclic |= parent_cyclic
        visiting.remove(iri)
        found = frozenset(branches)
        # A walk cut short at an ancestor can omit that ancestor's other exits.
        # Cache it only after a complete traversal from its own starting node.
        if not cyclic:
            branch_cache[iri] = found
        return found, cyclic

    result = []
    for cls in sorted(records.values(), key=lambda c: c.iri):
        branches, _ = walk_branches(cls.iri, set())
        branch_cache[cls.iri] = branches
        parent_labels = tuple(sorted({
            label for parent in cls.parents if parent in records
            for label, _ in records[parent].labels
        }))
        result.append(FolioClass(cls.iri, cls.labels, cls.definitions, cls.parents,
                                 parent_labels, tuple(sorted(branches))))
    return result
