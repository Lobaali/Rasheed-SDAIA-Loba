import pytest
from fastapi.testclient import TestClient

from rasheed.api.app import create_app
from rasheed.api.routes import get_scorer
from rasheed.domain.entities import Application, RawScore
from rasheed.service.scorer import ScholarshipScorer


class ConstantModel:
    def __init__(self, p: float, version: str = "test-1"):
        self._p = p
        self.model_version = version

    def predict_proba(self, features) -> RawScore:
        return RawScore(value=self._p)


@pytest.fixture
def client_factory():
    def _make(probability: float = 0.5, documents_complete: bool = True):
        app = create_app()
        scorer = ScholarshipScorer(model=ConstantModel(probability))
        app.dependency_overrides[get_scorer] = lambda: scorer
        return TestClient(app, raise_server_exceptions=False)
    return _make


@pytest.fixture(scope="session")
def real_model():
    from rasheed.adapters.sklearn_model import SklearnModel
    return SklearnModel.load("models/rasheed_lr_v1.joblib")


@pytest.fixture
def sample_application() -> Application:
    return Application(
        application_id="APP-TEST-0001", gpa=3.5, household_size=4,
        monthly_family_income_sar=4000.0, documents_complete=True,
    )