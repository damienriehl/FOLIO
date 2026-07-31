"""Monotonic record states for ontology review."""

from enum import StrEnum


class RecordState(StrEnum):
    DISCOVERED = "discovered"
    DETERMINISTIC_REJECTED = "deterministic_rejected"
    AWAITING_ASSESSMENT_SET = "awaiting_assessment_set"
    ACCEPTED = "accepted"
    DEFECT_CONFIRMED = "defect_confirmed"
    QUARANTINED = "quarantined"
    INCOMPLETE = "incomplete"
    STALE = "stale"
