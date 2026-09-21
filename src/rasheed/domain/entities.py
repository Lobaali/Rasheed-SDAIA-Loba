"""Pure domain entities. No I/O, no framework imports, no model imports.
This file must be importable with nothing but pydantic installed.
"""
from __future__ import annotations

import math
from enum import Enum

from pydantic import BaseModel, Field


class Decision(str, Enum):
    AUTO_ACCEPT = "auto_accept"
    COMMITTEE_REVIEW = "committee_review"
    REJECT = "reject"


class FeatureVector(BaseModel):
    """What the model actually sees. Deliberately does NOT include
    documents_complete: completeness is a hard business rule enforced
    in the policy layer, never something the model is allowed to
    override with a learned score. See DECISIONS.md.
    """

    values: dict[str, float]


class Application(BaseModel):
    """A single scholarship application, as received by the API."""

    application_id: str = Field(min_length=1, max_length=64)
    gpa: float = Field(ge=0.0, le=5.0)
    household_size: int = Field(ge=1, le=20)
    monthly_family_income_sar: float = Field(ge=0.0)
    documents_complete: bool

    def to_features(self) -> FeatureVector:
        income_per_capita = self.monthly_family_income_sar / self.household_size
        return FeatureVector(
            values={
                "gpa_normalised": self.gpa / 5.0,
                "log_income_per_capita": math.log1p(income_per_capita),
                "household_size": float(self.household_size),
            }
        )


class RawScore(BaseModel):
    """The model's raw output: probability the applicant is a strong
    candidate on academic/financial-need grounds, in [0, 1].
    """

    value: float = Field(ge=0.0, le=1.0)