"""The use-case orchestrator: takes an Application, drives it through
feature extraction -> model -> policy, and returns a result the API
can serialise. This is the ONE place that wires domain and model
together; everything downstream depends on this, never on sklearn.
"""
from __future__ import annotations

from pydantic import BaseModel

from rasheed.domain.entities import Application, Decision
from rasheed.domain.policies import decide
from rasheed.service.duplicate_checker import DuplicateChecker, NullDuplicateChecker
from rasheed.service.interfaces import Model


class ScoringResult(BaseModel):
    application_id: str
    decision: Decision
    score: float
    model_version: str
    duplicate_submission: bool = False


class ScholarshipScorer:
    def __init__(
        self,
        model: Model,
        *,
        accept_threshold: float | None = None,
        reject_threshold: float | None = None,
        min_gpa_for_auto_accept: float | None = None,
        duplicate_checker: DuplicateChecker | None = None,
    ):
        self._model = model
        self._accept_threshold = accept_threshold
        self._reject_threshold = reject_threshold
        self._min_gpa = min_gpa_for_auto_accept
        self._duplicate_checker = duplicate_checker or NullDuplicateChecker()

    def score(self, application: Application) -> ScoringResult:
        features = application.to_features()
        raw = self._model.predict_proba(features)

        kwargs = {}
        if self._accept_threshold is not None:
            kwargs["accept_threshold"] = self._accept_threshold
        if self._reject_threshold is not None:
            kwargs["reject_threshold"] = self._reject_threshold
        if self._min_gpa is not None:
            kwargs["min_gpa_for_auto_accept"] = self._min_gpa

        decision = decide(application, raw, **kwargs)

        is_duplicate = self._duplicate_checker.seen_recently(application.application_id)
        if is_duplicate and decision == Decision.AUTO_ACCEPT:
            decision = Decision.COMMITTEE_REVIEW

        self._duplicate_checker.mark_seen(application.application_id)

        return ScoringResult(
            application_id=application.application_id,
            decision=decision,
            score=raw.value,
            model_version=self._model.model_version,
            duplicate_submission=is_duplicate,
        )