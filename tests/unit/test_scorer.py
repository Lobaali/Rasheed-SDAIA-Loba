import pytest

from rasheed.domain.entities import Application, RawScore
from rasheed.service.scorer import ScholarshipScorer


class ConstantModel:
    def __init__(self, p: float, version: str = "test-1"):
        self._p = p
        self.model_version = version

    def predict_proba(self, features):
        return RawScore(value=self._p)


@pytest.mark.unit
def test_scorer_returns_model_version_and_score():
    app = Application(
        application_id="APP-1", gpa=3.0, household_size=2,
        monthly_family_income_sar=1000.0, documents_complete=True,
    )
    scorer = ScholarshipScorer(model=ConstantModel(0.5, version="v-test"))
    result = scorer.score(app)
    assert result.model_version == "v-test"
    assert result.score == 0.5
    assert result.application_id == "APP-1"