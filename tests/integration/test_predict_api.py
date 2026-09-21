import pathlib

import pytest
from fastapi.testclient import TestClient

from rasheed.api.app import app, create_app

MALFORMED = sorted(pathlib.Path("payloads/malformed").glob("*.json"))


@pytest.mark.integration
def test_predict_contract_auto_accept(client_factory, sample_application):
    client = client_factory(probability=0.9)
    r = client.post("/v1/predict", json=sample_application.model_dump())
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "auto_accept"
    assert "trace_id" in body


@pytest.mark.integration
def test_missing_documents_never_auto_rejects_even_via_api(client_factory, sample_application):
    client = client_factory(probability=0.01, documents_complete=False)
    payload = sample_application.model_dump()
    payload["documents_complete"] = False
    r = client.post("/v1/predict", json=payload)
    assert r.status_code == 200
    assert r.json()["decision"] == "committee_review"


@pytest.mark.integration
@pytest.mark.parametrize("payload_file", MALFORMED)
def test_malformed_corpus_rejected(client_factory, payload_file):
    r = client_factory().post(
        "/v1/predict", content=payload_file.read_bytes(),
        headers={"content-type": "application/json"},
    )
    assert 400 <= r.status_code < 500, payload_file.name


@pytest.mark.integration
def test_predict_500_hides_internal_details(client_factory, sample_application, monkeypatch):
    client = client_factory()

    def boom(self, application):
        raise ZeroDivisionError("seeded failure - should never reach the client")

    monkeypatch.setattr("rasheed.service.scorer.ScholarshipScorer.score", boom)
    r = client.post("/v1/predict", json=sample_application.model_dump())
    assert r.status_code == 500
    assert "ZeroDivisionError" not in r.text
    assert "seeded failure" not in r.text


@pytest.mark.integration
def test_health_endpoint(client_factory):
    r = client_factory().get("/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "rasheed"}


@pytest.mark.integration
def test_predict_503_when_model_not_ready():
    fresh_app = create_app()
    client = TestClient(fresh_app, raise_server_exceptions=False)
    r = client.post("/v1/predict", json={
        "application_id": "APP-1", "gpa": 3.0, "household_size": 3,
        "monthly_family_income_sar": 3000.0, "documents_complete": True,
    })
    assert r.status_code == 503
    assert r.headers.get("Retry-After") == "5"


@pytest.mark.integration
def test_ready_503_before_lifespan():
    fresh_app = create_app()
    client = TestClient(fresh_app, raise_server_exceptions=False)
    r = client.get("/v1/ready")
    assert r.status_code == 503


@pytest.mark.integration
def test_health_and_ready_with_real_lifespan():
    with TestClient(app) as client:
        r = client.get("/v1/ready")
        assert r.status_code == 200
        assert r.json() == {"status": "ready"}

@pytest.mark.integration
def test_malformed_response_has_trace_id(client_factory):
    r = client_factory().post("/v1/predict", json={"application_id": "APP-1"})
    assert r.status_code == 422
    body = r.json()
    assert "trace_id" in body
    assert body["error"] == "ValidationError"