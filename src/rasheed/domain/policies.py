"""Business policy: thresholds are BUSINESS decisions, not model
decisions. Named here so a risk/aid officer can review every number
without reading the function body.

Pure function => property-based-testable, reviewable by non-engineers.
"""

ACCEPT_THRESHOLD_DEFAULT = 0.75
REJECT_THRESHOLD_DEFAULT = 0.35
# Independent of the score: the score blends GPA with financial need
# (low income alone can push the score up), so this is a separate
# floor - a student can't be auto-accepted on need alone if their
# GPA itself doesn't clear this bar. Borderline academic cases still
# go to a human, even when overall eligibility looks strong.
MIN_GPA_FOR_AUTO_ACCEPT_DEFAULT = 2.0

from rasheed.domain.entities import Application, Decision, RawScore


def decide(
    application: Application,
    score: RawScore,
    *,
    accept_threshold: float = ACCEPT_THRESHOLD_DEFAULT,
    reject_threshold: float = REJECT_THRESHOLD_DEFAULT,
    min_gpa_for_auto_accept: float = MIN_GPA_FOR_AUTO_ACCEPT_DEFAULT,
) -> Decision:
    """The mandatory business rule (capstone Track A spec for Rasheed):
    a missing required document must ALWAYS route to committee review,
    never to an automatic, unexplained rejection - regardless of what
    the model scored. This check runs first and short-circuits the
    model-driven bands entirely.
    """
    if not application.documents_complete:
        return Decision.COMMITTEE_REVIEW

    if score.value >= accept_threshold and application.gpa >= min_gpa_for_auto_accept:
        return Decision.AUTO_ACCEPT

    if score.value <= reject_threshold:
        return Decision.REJECT

    return Decision.COMMITTEE_REVIEW