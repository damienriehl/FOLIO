"""Method v0.2: branch-aware lexical claims with heuristic confidence.

The suffix stemmer applies the first matching suffix only, in the documented
order below, and keeps at least three characters. It is intentionally small,
not a linguistic or probabilistic lemmatizer.
"""
from __future__ import annotations

from collections import defaultdict
import re
import unicodedata
from typing import Iterable

from .folio_forms import FOLIO_PREFIX, FolioClass, normalize, surface_forms
from .senses import Sense, sense_curie

METHOD_VERSION = 'opengloss-lexical/0.2'
BRANCH_PROFILES = {
    FOLIO_PREFIX + 'R9aSzp9cEiBCzObnP92jYFX': 'place',
    FOLIO_PREFIX + 'R8f4qGdjxuiQary8OBpq8W9': 'commerce',
    FOLIO_PREFIX + 'R767niCLQVC5zIcO5WDQMSl': 'finance',
    FOLIO_PREFIX + 'RhBgnef56iLBXYfPqWQE41': 'finance',
    FOLIO_PREFIX + 'RCIwc6WJi6IT7xePURxsi4T': 'finance',
    FOLIO_PREFIX + 'RDOvAHsvY8TKJ1O1orXPM9o': 'language',
    FOLIO_PREFIX + 'R79aItNTJQwHgR002wuX3iC': 'technical',
    FOLIO_PREFIX + 'R8EoZh39tWmXCkmP2Xzjl6E': 'technical',
    FOLIO_PREFIX + 'R8qItBwG2pRMFhUq1HQEMnb': 'technical',
    FOLIO_PREFIX + 'RDK1QEdQg1T8B5HQqMK2pZN': 'service',
}
PROFILE_PRIORS = {
    'legal': {'law_government': 1.0, 'business': 0.7, 'other': 0.3},
    'place': {'law_government': 1.0, 'nature': 1.0, 'people_society': 1.0,
              'history': 0.7, 'other': 0.3},
    'commerce': {'business': 1.0, 'science': 0.8, 'technology': 0.8,
                 'nature': 0.8, 'health': 0.8, 'arts': 0.8, 'everyday_life': 0.8,
                 'sports_recreation': 0.8, 'education': 0.8,
                 'law_government': 0.7, 'other': 0.3},
    'finance': {'business': 1.0, 'law_government': 0.8, 'mathematics': 0.7, 'other': 0.3},
    'language': {'language': 1.0, 'humanities': 0.8, 'people_society': 0.8, 'other': 0.3},
    'technical': {'technology': 1.0, 'language': 0.8, 'business': 0.7,
                  'law_government': 0.7, 'other': 0.3},
    'service': {'business': 1.0, 'law_government': 1.0, 'technology': 0.8,
                'health': 0.8, 'other': 0.3},
}
STOP_WORDS = frozenset('a an the and or but of for in on to under with without by at from as is are was were be been being that this these those it its which who whom between two more any into through'.split())
STEM_SUFFIXES = (('ies', 'y'), ('es', ''), ('s', ''), ('ing', ''), ('ed', ''), ('ly', ''), ('ment', ''))
MIN_STEM_LENGTH = 3
HEAD_PREPOSITIONS = frozenset(('of', 'for', 'in', 'on', 'to', 'under'))
MIN_LABEL_WORDS, MAX_LABEL_WORDS = 2, 6
PRIOR_WEIGHT, OVERLAP_WEIGHT = 0.5, 0.5
# The phrase floor admits business senses with modest gloss coverage (Landlord
# scores 0.406). The exact lead allows closely ranked sibling phrase senses,
# including the subtopics listed under breach of contract.
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


def domain_prior(sense: Sense, profiles: Iterable[str] = ('legal',)) -> float:
    root = sense.domain_root or sense.domain.split('.')[0]
    return max((PROFILE_PRIORS[p].get(root, PROFILE_PRIORS[p]['other'])
                for p in profiles), default=PROFILE_PRIORS['legal'].get(root, 0.3))


def sense_score(context: set[str], sense: Sense, profiles: Iterable[str] = ('legal',)) -> float:
    """Combine the domain prior with coverage of the gloss's content stems.

    FOLIO contexts (label, definition, and parent labels) are far longer than
    glosses, so Jaccard collapses toward zero and lets the domain prior alone
    decide every link. Gloss coverage does not penalize a longer context.
    """
    gloss = content_stems(sense.gloss)
    overlap = len(context & gloss) / len(gloss) if gloss else 0.0
    return PRIOR_WEIGHT * domain_prior(sense, profiles) + OVERLAP_WEIGHT * overlap


def candidate_headwords(classes: Iterable[FolioClass]) -> set[str]:
    return {word for cls in classes for form, _ in surface_forms(cls)
            for word in (form, *re.findall(r'[^\W_]+', form))}


def match(classes: Iterable[FolioClass], senses: Iterable[Sense]) -> tuple[list[dict], list[dict]]:
    index = defaultdict(list)
    for sense in senses:
        index[normalize(sense.headword)].append(sense)
    mappings = {}
    gaps = {}
    for cls in classes:
        profiles = tuple(sorted({BRANCH_PROFILES.get(branch, 'legal')
                                 for branch in cls.branches})) or ('legal',)
        context = content_stems(' '.join([cls.label, *cls.definitions, *cls.parent_labels]))
        ranked = {}
        class_mapped = False

        def rank(form: str) -> list[tuple[float, Sense]]:
            if form not in ranked:
                ranked[form] = sorted(((sense_score(context, s, profiles), s) for s in index[form]), key=lambda pair: (-pair[0], pair[1].sense_id))
            return ranked[form]

        def emit(
            sense: Sense, score: float, predicate: str, form: str,
            field: str, rule: str, factor: float = 1.0,
        ) -> None:
            nonlocal class_mapped
            confidence = round(factor * score, CONFIDENCE_DECIMALS)
            profile = min(profiles, key=lambda p: (-domain_prior(sense, (p,)), p))
            row = dict(
                subject_id=cls.subject_id, subject_label=cls.label,
                predicate_id=predicate, object_id=sense_curie(sense.sense_id),
                object_label=sense.headword, mapping_justification='semapv:LexicalMatching',
                confidence=f'{confidence:.3f}', subject_match_field=field,
                object_match_field='rdfs:label', match_string=form,
                comment=f'{rule}; score={score:.3f}; profile={profile}',
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
            words = re.findall(r'[^\W_]+', form)
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
            if available and not any(domain_prior(s, profiles) >= 0.7 for s in available):
                gaps[cls.subject_id, form] = dict(subject_id=cls.subject_id, subject_label=cls.label, match_string=form, headword_senses_domains='; '.join(f'{s.sense_id}={s.domain}' for s in sorted(available, key=lambda s: s.sense_id)))
    return sorted(mappings.values(), key=lambda r: (r['subject_id'], r['predicate_id'], r['object_id'])), [gaps[k] for k in sorted(gaps)]
