"""Load pinned OpenGloss nouns; pyarrow is needed only for parquet authoring."""
from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import json
from pathlib import Path
from typing import Iterable

from .folio_forms import normalize

COLUMNS = ('sense_id', 'lexeme_id', 'headword', 'pos', 'sense_index', 'domain', 'domain_root', 'gloss')
OGS_PREFIX = 'OGS:'


def sense_curie(sense_id: str) -> str:
    return OGS_PREFIX + sense_id


def raw_sense_id(curie: str) -> str:
    if not curie.startswith(OGS_PREFIX):
        raise ValueError(f'Expected an {OGS_PREFIX} sense CURIE: {curie!r}')
    return curie.removeprefix(OGS_PREFIX)


@dataclass(frozen=True)
class Sense:
    sense_id: str
    lexeme_id: str
    headword: str
    pos: str
    sense_index: int
    domain: str
    domain_root: str
    gloss: str


def sha256_file(path: str | Path) -> str:
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _senses(rows: Iterable[dict], headwords: set[str]) -> list[Sense]:
    selected = (
        Sense(**{
            f.name: int(row.get(f.name) or 0) if f.name == 'sense_index'
            else '' if row[f.name] is None else row[f.name]
            for f in fields(Sense)
        })
        for row in rows
        if row['pos'] == 'noun' and row.get('source') != 'wordnet-3.0'
        and normalize(row['headword']) in headwords
    )
    return sorted(selected, key=lambda s: s.sense_id)


def load_json(path: str | Path, headwords: set[str]) -> list[Sense]:
    return _senses(json.loads(Path(path).read_text(encoding='utf-8')), headwords)


def load_parquet(directory: str | Path, upstream: dict, headwords: set[str]) -> list[Sense]:
    paths = []
    # Verify all pins before importing pyarrow or opening any parquet reader.
    for pin in upstream['opengloss']['files']:
        path = Path(directory) / Path(pin['path']).name
        actual = sha256_file(path)
        if actual != pin['sha256']:
            raise ValueError(f"SHA256 mismatch for {path}: expected {pin['sha256']}, got {actual}")
        paths.append(path)
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    rows = []
    wanted = pa.array(sorted(headwords), type=pa.string())
    for path in paths:
        parquet = pq.ParquetFile(path)
        columns = list(COLUMNS) + (['source'] if 'source' in parquet.schema_arrow.names else [])
        for batch in parquet.iter_batches(columns=columns):
            table = pa.Table.from_batches([batch])
            normalized = pa.array([normalize(h or '') for h in table['headword'].to_pylist()])
            mask = pc.and_(pc.is_in(normalized, value_set=wanted), pc.equal(table['pos'], 'noun'))
            if 'source' in columns:
                mask = pc.and_(mask, pc.fill_null(pc.not_equal(table['source'], 'wordnet-3.0'), True))
            rows.extend(table.filter(mask).to_pylist())
    return _senses(rows, headwords)
