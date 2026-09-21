from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from rasheed.adapters.sklearn_model import SklearnModel
from rasheed.api.routes import router
from rasheed.api.schemas import ErrorEnvelope
from rasheed.config import Settings


class JsonLogFormatter(logging.Formatter):
    """Structured JSON logs correlated by trace id, no PII by design:
    callers only ever pass application_id (opaque), never names,
    income figures, or GPA in log fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        for key in ("trace_id", "application_id", "decision"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload)


def _configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger("rasheed")
    root.handlers = [handler]
    root.setLevel(level)
    root.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()  # type: ignore[call-arg]  # pydantic-settings fills required fields from env at runtime
    _configure_logging(settings.log_level)

    from rasheed.service.scorer import ScholarshipScorer

    t0 = time.perf_counter()
    model = SklearnModel.load(settings.model_path)

    duplicate_checker = None
    if settings.redis_url:
        import redis as redis_lib

        from rasheed.adapters.redis_duplicate_checker import RedisDuplicateChecker
        redis_client = redis_lib.from_url(settings.redis_url)
        duplicate_checker = RedisDuplicateChecker(redis_client)

    scorer = ScholarshipScorer(
        model=model,
        accept_threshold=settings.accept_threshold,
        reject_threshold=settings.reject_threshold,
        min_gpa_for_auto_accept=settings.min_gpa_for_auto_accept,
        duplicate_checker=duplicate_checker,
    )
    app.state.scorer = scorer

    from rasheed.domain.entities import Application
    warmup_app = Application(
        application_id="warmup", gpa=3.0, household_size=1,
        monthly_family_income_sar=1000.0, documents_complete=True,
    )
    scorer.score(warmup_app)
    logging.getLogger("rasheed").info("warmup_complete", extra={"trace_id": "startup"})

    logging.getLogger("rasheed").info("model_loaded", extra={"trace_id": "startup"})
    _ = time.perf_counter() - t0

    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Rasheed — Scholarship Screening", lifespan=lifespan)
    app.include_router(router)

    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers or {},
            content=ErrorEnvelope(
                error=type(exc).__name__, detail=str(exc.detail), trace_id=trace_id,
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=422,
            content=ErrorEnvelope(
                error="ValidationError", detail=str(exc.errors()), trace_id=trace_id,
            ).model_dump(),
        )

    return app


app = create_app()