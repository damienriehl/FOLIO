"""Method v0.1: deterministic lexical claims with heuristic confidence.

The suffix stemmer applies the first matching suffix only, in the documented
order below, and keeps at least three characters. It is intentionally small,
not a linguistic or probabilistic lemmatizer.
"""
from __future__ import annotations

from collections import defaultdict
import re
import unicodedata
from typing import Iterable

from .folio_forms import FolioClass, surface_forms
from .senses import Sense

METHOD_VERSION = 'opengloss-lexical/0.1'
STOP_WORDS = frozenset('a an the and or but of for in on to under with without by at from as is are was were be been being that this these those it its which who whom between two more any into through'.split())
STEM_SUFFIXES = (('ies', 'y'), ('es', ''), ('s', ''), ('ing', ''), ('ed', ''), ('ly', ''), ('ment', ''))
MIN_STEM_LENGTH = 3
HEAD_PREPOSITIONS = frozenset(('of', 'for', 'in', 'on', 'to', 'under'))
MIN_LABEL_WORDS, MAX_LABEL_WORDS = 2, 6
LEGAL_PRIOR, BUSINESS_PRIOR, OTHER_PRIOR = 1.0, 0.7, 0.3
PRIOR_WEIGHT, OVERLAP_WEIGHT = 0.5, 0.5
# Business scores are 0.35 + 0.5 * overlap; real glosses rarely cover 20% of
# a FOLIO context (Landlord scored 0.406), so the old floor dropped most property
# and commercial senses. Sibling phrase senses (breach of contract senses 1–3)
# also kept the main sense within 0.10 of its runner-up.
EXACT_THRESHOLD, EXACT_LEAD = 0.60, 0.05
OTHER_PHRASE_THRESHOLD, PHRASE_FLOOR = 0.55, 0.40
WORD_THRESHOLD, WORD_CONFIDENCE_FACTOR = 0.45, 0.8
CONFIDENCE_DECIMALS = 3
PREDICATE_STRENGTH = {'skos:exactMatch': 4, 'skos:closeMatch': 3, 'skos:broadMatch': 2, 'skos:narrowMatch': 2, 'skos:relatedMatch': 1}


def stem(word: str) -> str:
    for suffix, replacement in STEM_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) + len(replacement) >= MIN_STEM_LENGTH:
            return word[:-len(suffix)] + replacement
    return word


def content_stems(text: str) -> set[str]:
    return {stem(w) for w in re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', text).casefold()) if w not in STOP_WORDS}


def domain_prior(sense: Sense) -> float:
    root = sense.domain.split('.')[0]
    if root == 'law_government' or sense.domain_root == 'law_government':
        return LEGAL_PRIOR
    if root == 'business' or sense.domain_root == 'business':
        return BUSINESS_PRIOR
    return OTHER_PRIOR


def sense_score(context: set[str], sense: Sense) -> float:
    """Combine the domain prior with coverage of the gloss's content stems.

    FOLIO contexts (label, definition, and parent labels) are far longer than
    glosses, so Jaccard collapses toward zero and lets the domain prior alone
    decide every link. Gloss coverage does not penalize a longer context.
    """
    gloss = content_stems(sense.gloss)
    overlap = len(context & gloss) / len(gloss) if gloss else 0.0
    return PRIOR_WEIGHT * domain_prior(sense) + OVERLAP_WEIGHT * overlap


def candidate_headwords(classes: Iterable[FolioClass]) -> set[str]:
    return {word for cls in classes for form, _ in surface_forms(cls) for word in (form, *form.split())}


def match(classes: Iterable[FolioClass], senses: Iterable[Sense]) -> tuple[list[dict], list[dict]]:
    from .folio_forms import normalize
    index = defaultdict(list)
    for sense in senses:
        index[normalize(sense.headword)].append(sense)
    mappings = {}
    gaps = {}
    for cls in classes:
        context = content_stems(' '.join([cls.label, *cls.definitions, *cls.parent_labels]))
        ranked = {}
        class_mapped = False

        def rank(form: str) -> list[tuple[float, Sense]]:
            if form not in ranked:
                ranked[form] = sorted(((sense_score(context, s), s) for s in index[form]), key=lambda pair: (-pair[0], pair[1].sense_id))
            return ranked[form]

        def emit(
            sense: Sense, score: float, predicate: str, form: str,
            field: str, rule: str, factor: float = 1.0,
        ) -> None:
            nonlocal class_mapped
            confidence = round(factor * score, CONFIDENCE_DECIMALS)
            row = dict(
                subject_id=cls.subject_id, subject_label=cls.label,
                predicate_id=predicate, object_id='OGS:' + sense.sense_id,
                object_label=sense.headword, mapping_justification='semapv:LexicalMatching',
                confidence=f'{confidence:.3f}', subject_match_field=field,
                object_match_field='rdfs:label', match_string=form,
                comment=f'{rule}; score={score:.3f}',
            )
            key = (cls.subject_id, row['object_id'])
            old = mappings.get(key)
            strength = (PREDICATE_STRENGTH[predicate], confidence)
            if old is None or strength > (PREDICATE_STRENGTH[old['predicate_id']], float(old['confidence'])):
                mappings[key] = row
            class_mapped = True

        for form, field in surface_forms(cls):
            phrase = rank(form)
            if phrase:
                score, sense = phrase[0]
                if score >= PHRASE_FLOOR:
                    runner_score = phrase[1][0] if len(phrase) > 1 else 0.0
                    exact = field != 'skos:altLabel' and score >= EXACT_THRESHOLD and score >= runner_score + EXACT_LEAD
                    rule = 'altlabel-phrase' if field == 'skos:altLabel' else 'label-phrase'
                    emit(sense, score, 'skos:exactMatch' if exact else 'skos:closeMatch', form, field, rule)
                    for other_score, other in phrase[1:]:
                        if other_score >= OTHER_PHRASE_THRESHOLD:
                            emit(other, other_score, 'skos:closeMatch', form, field, rule)
            words = form.split()
            if MIN_LABEL_WORDS <= len(words) <= MAX_LABEL_WORDS:
                before = next((i for i, w in enumerate(words) if w in HEAD_PREPOSITIONS), None)
                head = words[before - 1] if before is not None and before > 0 else words[-1]
                for word in sorted(set(words) - STOP_WORDS):
                    atoms = rank(word)
                    if atoms and atoms[0][0] >= WORD_THRESHOLD:
                        score, sense = atoms[0]
                        emit(sense, score, 'skos:broadMatch' if word == head else 'skos:relatedMatch', word, field, 'head-word' if word == head else 'modifier-word', WORD_CONFIDENCE_FACTOR)
        if class_mapped:
            continue
        gap_forms = {normalize(label) for label, field in cls.labels
                     if field in ('rdfs:label', 'skos:prefLabel')}
        for form in sorted(gap_forms - {''}):
            available = index[form]
            if available:
                gaps[cls.subject_id, form] = dict(subject_id=cls.subject_id, subject_label=cls.label, match_string=form, headword_senses_domains='; '.join(f'{s.sense_id}={s.domain}' for s in sorted(available, key=lambda s: s.sense_id)))
    return sorted(mappings.values(), key=lambda r: (r['subject_id'], r['predicate_id'], r['object_id'])), [gaps[k] for k in sorted(gaps)]
