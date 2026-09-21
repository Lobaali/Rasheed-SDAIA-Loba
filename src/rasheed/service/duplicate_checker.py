"""EXTENSION: duplicate-submission detection.

If the same application_id is submitted twice within a short window,
that's suspicious enough to warrant human eyes - so the scorer
downgrades what would have been AUTO_ACCEPT to COMMITTEE_REVIEW and
flags it. Never auto-rejects on this alone.
"""
from __future__ import annotations

from typing import Protocol


class DuplicateChecker(Protocol):
    def seen_recently(self, application_id: str) -> bool: ...
    def mark_seen(self, application_id: str) -> None: ...


class NullDuplicateChecker:
    """Default no-op: used when no cache is configured. Feature is
    additive and optional - the service works correctly without it.
    """

    def seen_recently(self, application_id: str) -> bool:
        return False

    def mark_seen(self, application_id: str) -> None:
        return None