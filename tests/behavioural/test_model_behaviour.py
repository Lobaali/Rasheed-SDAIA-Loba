"""Tests against the REAL trained model. Marked slow: runs nightly /
pre-demo, never on every commit.
"""
import csv
import pathlib

import pytest

from rasheed.domain.entities import Application

pytestmark = [pytest.mark.behavioural, pytest.mark.slow]

GOLDEN_PATH = pathlib.Path("tests/behavioural/golden_scores_v1.csv")


def _score(model, application: Application) -> float:
    return model.predict_proba(application.to_features()).value


def test_invariance_to_application_id_value(real_model, sample_application):
    """The application_id is an opaque identifier - changing it must
    not move the score by even a tiny amount.
    """
    a = _score(real_model, sample_application)
    b = _score(real_model, sample_application.model_copy(
        update={"application_id": "SOME-OTHER-ID-9999"}))
    assert a == pytest.approx(b, abs=1e-9)


def test_directional_gpa_increases_eligibility(real_model, sample_application):
    """All else equal, a higher GPA must never lower the eligibility
    score - the exact shape of test the capstone spec asks for.
    """
    low_gpa = _score(real_model, sample_application.model_copy(update={"gpa": 1.0}))
    high_gpa = _score(real_model, sample_application.model_copy(update={"gpa": 4.5}))
    assert high_gpa >= low_gpa - 1e-6


def test_golden_reference_scores_unchanged():
    """Scores the reference set with the CURRENT model and compares to
    the versioned golden file. Any diff means either an unintended
    training/serving skew, or a real model change that must be
    reviewed and the golden file regenerated deliberately.
    """
    from rasheed.adapters.sklearn_model import SklearnModel
    model = SklearnModel.load("models/rasheed_lr_v1.joblib")

    with open(GOLDEN_PATH) as f:
        reader = csv.DictReader(f)
        mismatches = []
        for row in reader:
            app = Application(
                application_id=row["application_id"], gpa=float(row["gpa"]),
                household_size=int(row["household_size"]),
                monthly_family_income_sar=float(row["monthly_family_income_sar"]),
                documents_complete=True,
            )
            actual = _score(model, app)
            expected = float(row["score"])
            if abs(actual - expected) > 1e-6:
                mismatches.append((row["application_id"], expected, actual))

    assert not mismatches, f"{len(mismatches)} golden-score mismatches: {mismatches[:5]}"