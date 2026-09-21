from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from rasheed.api.schemas import ApplicationRequest, PredictResponse
from rasheed.domain.entities import Application
from rasheed.service.scorer import ScholarshipScorer

router = APIRouter()
logger = logging.getLogger("rasheed")


def get_scorer(request: Request) -> ScholarshipScorer:
    """The DI seam. In tests, app.dependency_overrides[get_scorer]
    replaces this whole function - the real body never runs there.
    """
    scorer = getattr(request.app.state, "scorer", None)
    if scorer is None:
        raise HTTPException(
            status_code=503, detail="Model not loaded yet",
            headers={"Retry-After": "5"},
        )
    return scorer


@router.get("/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "rasheed"}


@router.get("/v1/ready")
def ready(request: Request, response: Response) -> dict:
    if getattr(request.app.state, "scorer", None) is None:
        response.status_code = 503
        return {"status": "not_ready"}
    return {"status": "ready"}


@router.post("/v1/predict", response_model=PredictResponse)
def predict(
    req: ApplicationRequest,
    request: Request,
    scorer: ScholarshipScorer = Depends(get_scorer),
) -> PredictResponse:
    trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
    application = Application(**req.model_dump())

    try:
        result = scorer.score(application)
    except Exception:
        logger.exception(
            "scoring_failed",
            extra={"trace_id": trace_id, "application_id": application.application_id},
        )
        raise HTTPException(status_code=500, detail="Internal error while scoring the application")

    logger.info(
        "scored",
        extra={"trace_id": trace_id, "application_id": application.application_id,
               "decision": result.decision.value},
    )
    return PredictResponse(
        application_id=result.application_id,
        decision=result.decision,
        score=result.score,
        model_version=result.model_version,
        trace_id=trace_id,
        duplicate_submission=result.duplicate_submission,
    )