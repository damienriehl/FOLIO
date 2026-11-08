"""Offline contract tests for the deterministic OpenGloss builder."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
FIXTURES = ROOT / 'tests/fixtures/opengloss/build'


def build(directory: Path):
    paths = [directory / name for name in ('m.tsv', 's.tsv', 'g.tsv')]
    result = subprocess.run([
        sys.executable, str(ROOT / 'scripts/build_opengloss_mappings.py'),
        '--folio', str(FIXTURES / 'folio-mini.owl'),
        '--senses-json', str(FIXTURES / 'senses-mini.json'),
        '--out', str(paths[0]), '--senses-out', str(paths[1]),
        '--gaps-out', str(paths[2]), '--mapping-date', '2026-11-08',
        '--folio-version', 'fixture; sha256:fixture',
    ], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.strip().splitlines()) == 1
    raw = paths[0].read_text()
    header = yaml.safe_load('\n'.join(line[2:] for line in raw.splitlines() if line.startswith('# ')))
    rows = list(csv.DictReader(io.StringIO('\n'.join(line for line in raw.splitlines() if not line.startswith('#'))), delimiter='\t'))
    return paths, header, rows


def test_build_contract(tmp_path):
    paths, header, rows = build(tmp_path / 'first')
    _, _, second = build(tmp_path / 'second')
    for path in paths:
        assert path.read_bytes() == (tmp_path / 'second' / path.name).read_bytes()
    required = 'curie_map mapping_set_id mapping_set_version mapping_set_title mapping_set_description license mapping_date mapping_tool mapping_tool_version subject_source subject_source_version object_source object_source_version'.split()
    assert set(required) <= header.keys()
    assert header['object_source_version'].startswith('mjbommar/opengloss-v2.4-senses@')
    assert 'extension_definitions' not in header
    assert set(header) == set(required)
    assert rows == second
    assert rows == sorted(rows, key=lambda r: (r['subject_id'], r['predicate_id'], r['object_id']))
    assert len({(r['subject_id'], r['object_id']) for r in rows}) == len(rows)
    links = {(r['subject_id'], r['object_id']): r for r in rows}
    for sense, predicate in [('breach_of_contract:noun:0', 'exactMatch'), ('breach:noun:1', 'broadMatch'), ('contract:noun:0', 'relatedMatch')]:
        assert links['FOLIO:breach', 'OGS:' + sense]['predicate_id'] == 'skos:' + predicate
    assert ('FOLIO:breach', 'OGS:breach:noun:0') not in links
    assert ('FOLIO:tenant', 'OGS:tenant:noun:0') in links
    assert ('FOLIO:tenant', 'OGS:tenant:noun:1') not in links
    assert all(r['object_id'] != 'OGS:property:noun:0' for r in rows)
    assert all(r['subject_id'] != 'FOLIO:deprecated' for r in rows)
    assert all(r['object_id'] != 'OGS:locataire:noun:0' for r in rows)
    assert links['FOLIO:alias', 'OGS:contract:noun:0']['predicate_id'] == 'skos:closeMatch'
    assert links['FOLIO:landlord', 'OGS:landlord:noun:0']['predicate_id'] in ('skos:closeMatch', 'skos:exactMatch')
    assert links['FOLIO:landlord', 'OGS:landlord:noun:0']['confidence'] == '0.406'
    gaps = list(csv.DictReader(paths[2].open(), delimiter='\t'))
    assert gaps == [dict(subject_id='FOLIO:property', subject_label='Property', match_string='property',
                         headword_senses_domains='property:noun:0=science.materials_science')]
    senses = list(csv.DictReader(paths[1].open(), delimiter='\t'))
    assert [s['sense_id'] for s in senses] == sorted({r['object_id'][4:] for r in rows})
    assert all('owl:sameAs' not in p.read_text() and 'owl:equivalentClass' not in p.read_text() for p in paths)


def test_forms():
    from opengloss_mapping.folio_forms import load_folio, surface_forms, normalize
    classes = {c.iri.rsplit('/', 1)[-1]: c for c in load_folio(FIXTURES / 'folio-mini.owl')}
    assert 'deprecated' not in classes
    assert ('license', 'rdfs:label') in surface_forms(classes['license'])
    assert {f for f, _ in surface_forms(classes['agreements'])} == {'agreements contracts', 'agreements', 'contracts'}
    assert all(f != 'locataire' for f, _ in surface_forms(classes['tenant']))
    assert normalize(' ＬＩＣＥＮＳＥ_test/A-B (One) (Two) ') == 'license test a b (one)'


def test_hash_mismatch_before_parquet_read(tmp_path):
    from opengloss_mapping.senses import load_parquet
    (tmp_path / 'shard.parquet').write_bytes(b'not parquet')
    pins = {'opengloss': {'files': [{'path': 'data/shard.parquet', 'sha256': '0' * 64}]}}
    with pytest.raises(ValueError, match='SHA256 mismatch.*shard.parquet'):
        load_parquet(tmp_path, pins, {'tenant'})


def test_fixture_nouns_and_normalization(tmp_path):
    from opengloss_mapping.senses import load_json
    path = tmp_path / 'senses.json'
    path.write_text(json.dumps([
        dict(sense_id='a:noun:0', lexeme_id='a:noun', headword='REAL_Property', pos='noun', sense_index=0, domain='business.real_estate', domain_root='business', gloss='Land'),
        dict(sense_id='a:verb:0', lexeme_id='a:verb', headword='real property', pos='verb', sense_index=0, domain='business', domain_root='business', gloss='Land'),
    ]))
    assert [s.sense_id for s in load_json(path, {'real property'})] == ['a:noun:0']


def test_rank_ties_secondary_threshold_and_altlabel_cap():
    from opengloss_mapping.folio_forms import FolioClass
    from opengloss_mapping.matcher import match
    from opengloss_mapping.senses import Sense
    senses = [Sense(f'tenant:noun:{i}', 'tenant:noun', 'tenant', 'noun', i,
                    'law_government.civil_law', 'law_government', 'Tenant') for i in (1, 0)]
    cls = FolioClass('https://folio.openlegalstandard.org/t', (('Tenant', 'rdfs:label'),))
    rows, gaps = match([cls], senses)
    assert len(rows) == 2
    assert all(r['predicate_id'] == 'skos:closeMatch' for r in rows)
    assert [r['object_id'] for r in rows] == ['OGS:tenant:noun:0', 'OGS:tenant:noun:1']
    assert match([cls], senses) == match([cls], reversed(senses))
    alias = FolioClass(cls.iri, (('Tenant', 'skos:altLabel'),))
    rows, _ = match([alias], senses[:1])
    assert rows[0]['predicate_id'] == 'skos:closeMatch'
    assert rows[0]['comment'] == 'altlabel-phrase; score=1.000'
    # Legal prior alone allows only the best phrase sense at 0.500;
    # the other sense does not clear the 0.550 secondary threshold.
    unrelated = [Sense(s.sense_id, s.lexeme_id, s.headword, s.pos, s.sense_index,
                       s.domain, s.domain_root, 'Completely different') for s in senses]
    rows, _ = match([cls], unrelated)
    assert len(rows) == 1 and rows[0]['object_id'] == 'OGS:tenant:noun:0'
    assert rows[0]['confidence'] == '0.500'


def test_strongest_predicate_wins_over_word_and_alias():
    from opengloss_mapping.folio_forms import FolioClass
    from opengloss_mapping.matcher import match
    from opengloss_mapping.senses import Sense
    cls = FolioClass('https://folio.openlegalstandard.org/t',
                     (('Tenant', 'rdfs:label'), ('Tenant', 'skos:altLabel'),
                      ('Building Tenant', 'skos:prefLabel')),
                     ('Tenant building',))
    sense = Sense('tenant:noun:0', 'tenant:noun', 'Tenant', 'noun', 0,
                  'law_government.civil_law', 'law_government', 'Tenant building')
    rows, _ = match([cls], [sense])
    assert len(rows) == 1
    assert rows[0]['predicate_id'] == 'skos:exactMatch'
    assert rows[0]['subject_match_field'] == 'rdfs:label'
    assert rows[0]['confidence'] == '1.000'


def test_low_score_never_links_and_writer_cleans_text(tmp_path):
    from opengloss_mapping.folio_forms import FolioClass
    from opengloss_mapping.matcher import match, stem
    from opengloss_mapping.senses import Sense
    from opengloss_mapping.sssom_writer import write_senses, write_gaps
    assert stem('parties') == 'party'
    assert stem('gas') == 'gas'
    cls = FolioClass('https://folio.openlegalstandard.org/p', (('Property', 'rdfs:label'),))
    sense = Sense('property:noun:0', 'property:noun', 'Property', 'noun', 0,
                  'science.materials_science', 'science', 'Measurable attribute')
    rows, gaps = match([cls], [sense])
    assert rows == [] and len(gaps) == 1
    write_senses(tmp_path / 's.tsv', [sense], [{'object_id': 'OGS:property:noun:0'}])
    dirty = [{**gaps[0], 'subject_label': 'Property\twith\r\nnewlines'}]
    write_gaps(tmp_path / 'g.tsv', dirty)
    output = list(csv.DictReader((tmp_path / 'g.tsv').open(), delimiter='\t'))
    assert output[0]['subject_label'] == 'Property with  newlines'
    assert b'\r' not in (tmp_path / 'g.tsv').read_bytes()


def test_json_excludes_wordnet(tmp_path):
    from opengloss_mapping.senses import load_json
    senses = json.loads((FIXTURES / 'senses-mini.json').read_text())
    senses[0]['source'] = 'wordnet-3.0'
    path = tmp_path / 'sources.json'
    path.write_text(json.dumps(senses))
    assert all(s.sense_id != senses[0]['sense_id'] for s in load_json(path, {'breach'}))


def test_null_senses_build_with_other_prior(tmp_path):
    from opengloss_mapping.matcher import domain_prior, sense_score, content_stems
    from opengloss_mapping.senses import load_json
    senses = load_json(FIXTURES / 'senses-mini.json', {'unclassified term'})
    populated, empty = senses
    assert populated.domain == populated.domain_root == populated.lexeme_id == ''
    assert populated.sense_index == 0 and isinstance(populated.sense_index, int)
    assert empty.gloss == ''
    assert all(domain_prior(s) == 0.3 for s in senses)
    assert sense_score(content_stems('Unclassified term'), populated) == pytest.approx(0.65)
    assert sense_score(content_stems('Unclassified term'), empty) == pytest.approx(0.15)
    paths, _, rows = build(tmp_path)
    row = next(r for r in rows if r['object_id'] == 'OGS:unclassified_term:noun:0')
    assert row['predicate_id'] == 'skos:exactMatch'
    assert row['confidence'] == '0.650'
    assert all(r['object_id'] != 'OGS:unclassified_term:noun:1' for r in rows)
    sidecar = list(csv.DictReader(paths[1].open(), delimiter='\t'))
    sense = next(s for s in sidecar if s['sense_id'] == 'unclassified_term:noun:0')
    assert sense['domain'] == sense['lexeme_id'] == ''
    assert sense['sense_index'] == '0'


@pytest.mark.parametrize('sense_index', [None, '2', 3])
def test_sense_index_is_an_integer(tmp_path, sense_index):
    from opengloss_mapping.senses import load_json
    row = json.loads((FIXTURES / 'senses-mini.json').read_text())[0]
    row['sense_index'] = sense_index
    path = tmp_path / 'senses.json'
    path.write_text(json.dumps([row]))
    sense, = load_json(path, {'breach'})
    assert sense.sense_index == (0 if sense_index is None else int(sense_index))
    assert isinstance(sense.sense_index, int)
    del row['sense_index']
    path.write_text(json.dumps([row]))
    sense, = load_json(path, {'breach'})
    assert sense.sense_index == 0 and isinstance(sense.sense_index, int)


def test_material_breach_head_word(tmp_path):
    _, _, rows = build(tmp_path)
    links = {r['object_id']: r for r in rows if r['subject_id'] == 'FOLIO:material-breach'}
    assert links['OGS:breach:noun:1']['predicate_id'] == 'skos:broadMatch'
    assert links['OGS:breach:noun:1']['comment'].startswith('head-word;')
    assert links['OGS:material:noun:0']['predicate_id'] == 'skos:relatedMatch'
    assert links['OGS:material:noun:0']['comment'].startswith('modifier-word;')


@pytest.mark.parametrize('label, head', [
    ('Material Breach ' + prep + ' Contract', 'breach')
    for prep in ('of', 'for', 'in', 'on', 'to', 'under')
] + [
    ('Breach of Contract', 'breach'),
    ('Material Breach', 'breach'),
    ('In Breach of Contract', 'contract'),
    ('Material Breach of Contract under Law', 'breach'),
])
def test_first_preposition_head_rule(label, head):
    from opengloss_mapping.folio_forms import FolioClass
    from opengloss_mapping.matcher import match
    from opengloss_mapping.senses import Sense
    cls = FolioClass('https://folio.openlegalstandard.org/t', ((label, 'rdfs:label'),))
    senses = [Sense(word + ':noun:0', word + ':noun', word, 'noun', 0,
                    'law_government', 'law_government', word)
              for word in ('material', 'breach', 'contract', 'law')]
    rows, _ = match([cls], senses)
    broad = [r['object_label'] for r in rows if r['predicate_id'] == 'skos:broadMatch']
    assert broad == [head]
    assert all(r['predicate_id'] == 'skos:relatedMatch' for r in rows if r['object_label'] != head)


def test_score_uses_gloss_coverage():
    from opengloss_mapping.matcher import content_stems, sense_score
    from opengloss_mapping.senses import Sense
    sense = Sense('contract:noun:0', 'contract:noun', 'contract', 'noun', 0,
                  'law_government', 'law_government', 'Contracts and obligations')
    context = content_stems('Contract agreement parties enforceable promise performance')
    assert sense_score(context, sense) == pytest.approx(0.75)
    assert sense_score(context | content_stems('Extra lengthy definition with many unrelated words'), sense) == pytest.approx(0.75)
    assert sense_score(context | content_stems('Obligation'), sense) == 1.0


@pytest.mark.parametrize('gloss', ['', 'the and of'])
def test_empty_gloss_has_zero_overlap(gloss):
    from opengloss_mapping.matcher import content_stems, sense_score
    from opengloss_mapping.senses import Sense
    sense = Sense('contract:noun:0', 'contract:noun', 'contract', 'noun', 0,
                  'law_government', 'law_government', gloss)
    assert sense_score(content_stems('Contract'), sense) == 0.5
    assert sense_score(set(), sense) == 0.5


def test_breach_phrase_exact_with_seven_point_lead():
    from opengloss_mapping.folio_forms import FolioClass
    from opengloss_mapping.matcher import content_stems, match, sense_score
    from opengloss_mapping.senses import Sense
    definition = 'Failure to fulfill a contractual obligation or covenant'
    cls = FolioClass('https://folio.openlegalstandard.org/breach',
                     (('Breach of Contract', 'rdfs:label'),), (definition,))
    senses = [Sense(f'breach_of_contract:noun:{i}', 'breach_of_contract:noun',
                    'breach of contract', 'noun', i, 'law_government.civil_law',
                    'law_government', gloss)
              for i, gloss in enumerate((definition, definition + ' contract damages'))]
    context = content_stems(cls.label + ' ' + definition)
    assert sense_score(context, senses[0]) - sense_score(context, senses[1]) == pytest.approx(0.07, abs=0.002)
    rows, gaps = match([cls], senses)
    best = next(r for r in rows if r['object_id'] == 'OGS:breach_of_contract:noun:0')
    assert best['predicate_id'] == 'skos:exactMatch'
    assert gaps == []


def test_word_only_mapping_suppresses_class_gap():
    from opengloss_mapping.folio_forms import FolioClass
    from opengloss_mapping.matcher import match
    from opengloss_mapping.senses import Sense
    cls = FolioClass('https://folio.openlegalstandard.org/interest',
                     (('Rental Interest', 'rdfs:label'),))
    senses = [
        Sense('rental_interest:noun:0', 'rental_interest:noun', 'rental interest',
              'noun', 0, 'science', 'science', 'Microscopic particle'),
        Sense('interest:noun:0', 'interest:noun', 'interest', 'noun', 0,
              'business.finance', 'business', 'Interest return money capital'),
    ]
    rows, gaps = match([cls], senses)
    assert len(rows) == 1
    assert rows[0]['object_id'] == 'OGS:interest:noun:0'
    assert rows[0]['predicate_id'] == 'skos:broadMatch'
    assert rows[0]['comment'] == 'head-word; score=0.475'
    assert gaps == []


def test_gaps_use_only_whole_labels_and_preflabels():
    from opengloss_mapping.folio_forms import FolioClass
    from opengloss_mapping.matcher import match
    from opengloss_mapping.senses import Sense
    cls = FolioClass('https://folio.openlegalstandard.org/p', (
        ('Unknown Property', 'rdfs:label'), (' ＰＲＯＰＥＲＴＹ (Legal)', 'skos:prefLabel'),
        ('Property', 'skos:prefLabel'), ('Attribute', 'skos:altLabel'),
        ('Quality / Attribute', 'rdfs:label'),
    ))
    senses = [Sense(word + ':noun:0', word + ':noun', word, 'noun', 0,
                    'science.materials_science', 'science', 'Measurable substance')
              for word in ('property', 'attribute', 'quality')]
    rows, gaps = match([cls], senses)
    assert rows == []
    assert gaps == [dict(subject_id='FOLIO:p', subject_label='Unknown Property',
                         match_string='property',
                         headword_senses_domains='property:noun:0=science.materials_science')]
    words_only = FolioClass(cls.iri, (('Unknown Property', 'rdfs:label'), ('Attribute', 'skos:altLabel')))
    assert match([words_only], senses) == ([], [])
