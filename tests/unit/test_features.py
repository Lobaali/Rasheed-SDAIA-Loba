import math

import pytest

from rasheed.domain.entities import Application


@pytest.mark.unit
def test_to_features_shape():
    app = Application(
        application_id="APP-1", gpa=4.0, household_size=2,
        monthly_family_income_sar=2000.0, documents_complete=True,
    )
    fv = app.to_features()
    assert set(fv.values.keys()) == {"gpa_normalised", "log_income_per_capita", "household_size"}
    assert fv.values["gpa_normalised"] == pytest.approx(0.8)
    assert fv.values["household_size"] == 2.0


@pytest.mark.unit
def test_to_features_income_per_capita_math():
    app = Application(
        application_id="APP-1", gpa=2.5, household_size=4,
        monthly_family_income_sar=4000.0, documents_complete=True,
    )
    fv = app.to_features()
    expected = math.log1p(1000.0)
    assert fv.values["log_income_per_capita"] == pytest.approx(expected)


@pytest.mark.unit
def test_documents_complete_never_enters_the_feature_vector():
    app = Application(
        application_id="APP-1", gpa=3.0, household_size=1,
        monthly_family_income_sar=1000.0, documents_complete=False,
    )
    fv = app.to_features()
    assert "documents_complete" not in fv.values