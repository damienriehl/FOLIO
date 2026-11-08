"""Stable UTF-8 SSSOM serialization and its sense and gap sidecars."""
from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

import yaml

from .senses import Sense

CURIE_MAP = {
    'FOLIO': 'https://folio.openlegalstandard.org/',
    'OGS': 'tag:folio.openlegalstandard.org,2026:opengloss/sense/',
    'OGL': 'tag:folio.openlegalstandard.org,2026:opengloss/lexeme/',
    'skos': 'http://www.w3.org/2004/02/skos/core#',
    'semapv': 'https://w3id.org/semapv/vocab/',
    'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
    'sssom': 'https://w3id.org/sssom/',
}
MAPPING_SET_ID = 'https://folio.openlegalstandard.org/mappings/opengloss'
COLUMNS = ('subject_id', 'subject_label', 'predicate_id', 'object_id', 'object_label', 'mapping_justification', 'confidence', 'subject_match_field', 'object_match_field', 'match_string', 'comment')
SENSE_COLUMNS = ('sense_id', 'lexeme_id', 'headword', 'pos', 'sense_index', 'domain', 'gloss')
GAP_COLUMNS = ('subject_id', 'subject_label', 'match_string', 'headword_senses_domains')


def clean(value: object) -> str:
    return str(value).replace('\t', ' ').replace('\r', ' ').replace('\n', ' ')


def _write(path: str | Path, columns: tuple[str, ...], rows: Iterable[dict], header: dict | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as stream:
        if header is not None:
            for line in yaml.safe_dump(header, sort_keys=False, allow_unicode=True).splitlines():
                stream.write('# ' + line + '\n')
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({key: clean(row[key]) for key in columns})


def write_sssom(path: str | Path, header: dict, rows: list[dict]) -> None:
    _write(path, COLUMNS, sorted(rows, key=lambda r: (r['subject_id'], r['predicate_id'], r['object_id'])), header)


def write_senses(path: str | Path, senses: Iterable[Sense], rows: list[dict]) -> None:
    used = {r['object_id'][4:] for r in rows}
    unique = {s.sense_id: s for s in senses if s.sense_id in used}
    _write(path, SENSE_COLUMNS, (asdict(unique[k]) for k in sorted(unique)))


def write_gaps(path: str | Path, gaps: list[dict]) -> None:
    _write(path, GAP_COLUMNS, sorted(gaps, key=lambda r: (r['subject_id'], r['subject_label'], r['match_string'], r['headword_senses_domains'])))
