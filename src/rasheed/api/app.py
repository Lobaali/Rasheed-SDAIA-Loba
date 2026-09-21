from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
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
    settings = Settings()
    _configure_logging(settings.log_level)

    from rasheed.service.scorer import ScholarshipScorer

    t0 = time.perf_counter()
    model = SklearnModel.load(settings.model_path)
    scorer = ScholarshipScorer(
        model=model,
        accept_threshold=settings.accept_threshold,
        reject_threshold=settings.reject_threshold,
        min_gpa_for_auto_accept=settings.min_gpa_for_auto_accept,
    )
    app.state.scorer = scorer
    logging.getLogger("rasheed").info("model_loaded", extra={"trace_id": "startup"})
    _ = time.perf_counter() - t0

    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Rasheed — Scholarship Screening", lifespan=lifespan)
    app.include_router(router)

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

    return app


app = create_app()