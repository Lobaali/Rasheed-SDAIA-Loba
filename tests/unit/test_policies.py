import pytest

from rasheed.domain.entities import Application, Decision, RawScore
from rasheed.domain.policies import decide


def _app(**overrides) -> Application:
    base = {
        "application_id": "APP-0001", "gpa": 3.5, "household_size": 4,
        "monthly_family_income_sar": 4000.0, "documents_complete": True,
    }
    base.update(overrides)
    return Application(**base)


@pytest.mark.unit
def test_missing_documents_always_routes_to_review_never_auto_reject():
    """The capstone's mandatory Rasheed behavioural rule: a missing
    required document must ALWAYS go to committee review, even when
    the model score alone would have said REJECT.
    """
    app = _app(documents_complete=False, gpa=0.5)
    score = RawScore(value=0.01)  # model would say REJECT on its own
    assert decide(app, score) is Decision.COMMITTEE_REVIEW


@pytest.mark.unit
@pytest.mark.parametrize("score_value, gpa, expected", [
    (0.80, 3.0, Decision.AUTO_ACCEPT),
    (0.75, 2.0, Decision.AUTO_ACCEPT),        # boundary inclusive
    (0.75, 1.99, Decision.COMMITTEE_REVIEW),  # high score, low GPA
    (0.50, 3.0, Decision.COMMITTEE_REVIEW),
    (0.35, 3.0, Decision.REJECT),             # boundary inclusive
    (0.34, 3.0, Decision.REJECT),
    (0.0, 3.0, Decision.REJECT),
    (1.0, 3.0, Decision.AUTO_ACCEPT),
])
def test_decision_bands(score_value, gpa, expected):
    app = _app(gpa=gpa, documents_complete=True)
    assert decide(app, RawScore(value=score_value)) is expected