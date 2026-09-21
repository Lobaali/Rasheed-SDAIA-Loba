"""The only file in this codebase that imports sklearn. Implements
the Model Protocol so the rest of the app never knows sklearn exists.
"""
from __future__ import annotations

import joblib

from rasheed.domain.entities import FeatureVector, RawScore


class SklearnModel:
    def __init__(self, sklearn_model, feature_order: list[str], model_version: str):
        self._model = sklearn_model
        self._feature_order = feature_order
        self.model_version = model_version

    @classmethod
    def load(cls, path: str) -> SklearnModel:
        bundle = joblib.load(path)
        return cls(
            sklearn_model=bundle["sklearn_model"],
            feature_order=bundle["feature_order"],
            model_version=bundle["model_version"],
        )

    def predict_proba(self, features: FeatureVector) -> RawScore:
        row = [[features.values[name] for name in self._feature_order]]
        proba = self._model.predict_proba(row)[0][1]
        return RawScore(value=float(proba))