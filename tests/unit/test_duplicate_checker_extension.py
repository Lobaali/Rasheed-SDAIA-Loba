import pytest

from rasheed.domain.entities import Application, RawScore
from rasheed.service.scorer import ScholarshipScorer


class InMemoryDuplicateChecker:
    def __init__(self, already_seen: set[str] | None = None):
        self._seen = already_seen or set()

    def seen_recently(self, application_id: str) -> bool:
        return application_id in self._seen

    def mark_seen(self, application_id: str) -> None:
        self._seen.add(application_id)


class ConstantModel:
    def __init__(self, p: float, version: str = "test-1"):
        self._p = p
        self.model_version = version

    def predict_proba(self, features):
        return RawScore(value=self._p)


def _app(**overrides) -> Application:
    base = {
        "application_id": "APP-DUP-1", "gpa": 4.0, "household_size": 2,
        "monthly_family_income_sar": 2000.0, "documents_complete": True,
    }
    base.update(overrides)
    return Application(**base)


@pytest.mark.unit
def test_repeat_submission_downgrades_auto_accept_to_review():
    checker = InMemoryDuplicateChecker(already_seen={"APP-DUP-1"})
    scorer = ScholarshipScorer(model=ConstantModel(0.95), duplicate_checker=checker)
    result = scorer.score(_app())
    assert result.decision.value == "committee_review"
    assert result.duplicate_submission is True


@pytest.mark.unit
def test_first_submission_is_not_flagged_as_duplicate():
    checker = InMemoryDuplicateChecker()
    scorer = ScholarshipScorer(model=ConstantModel(0.95), duplicate_checker=checker)
    result = scorer.score(_app())
    assert result.decision.value == "auto_accept"
    assert result.duplicate_submission is False


@pytest.mark.unit
def test_duplicate_never_auto_rejects_only_downgrades_from_accept():
    """A duplicate on a REJECT-band score stays REJECT - the extension
    only ever pulls DOWN from auto-accept, never toward reject.
    """
    checker = InMemoryDuplicateChecker(already_seen={"APP-DUP-1"})
    scorer = ScholarshipScorer(model=ConstantModel(0.10), duplicate_checker=checker)
    result = scorer.score(_app())
    assert result.decision.value == "reject"