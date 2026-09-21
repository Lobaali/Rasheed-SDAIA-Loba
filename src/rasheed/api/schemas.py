from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from rasheed.domain.entities import Decision


class ApplicationRequest(BaseModel):
    # strict=True closes a real gap: pydantic's default (lenient) mode
    # coerces strings like "yes"/"1" into bool, silently accepting bad
    # input. Strict mode makes that a validation error instead.
    model_config = ConfigDict(extra="forbid", strict=True)

    application_id: str = Field(min_length=1, max_length=64)
    gpa: float = Field(ge=0.0, le=5.0)
    household_size: int = Field(ge=1, le=20)
    monthly_family_income_sar: float = Field(ge=0.0)
    documents_complete: bool


class PredictResponse(BaseModel):
    application_id: str
    decision: Decision
    score: float
    model_version: str
    trace_id: str
    duplicate_submission: bool = False


class ErrorEnvelope(BaseModel):
    error: str
    detail: str
    trace_id: str