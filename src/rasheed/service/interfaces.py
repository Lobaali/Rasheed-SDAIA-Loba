"""The seam. Anything conforming to this Protocol can stand in as the
model: the real sklearn adapter in production, ConstantModel in tests.
Neither the service layer nor the API ever imports sklearn directly.
"""
from __future__ import annotations

from typing import Protocol

from rasheed.domain.entities import FeatureVector, RawScore


class Model(Protocol):
    model_version: str

    def predict_proba(self, features: FeatureVector) -> RawScore: ...