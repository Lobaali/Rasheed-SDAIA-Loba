"""The only file that imports redis. Implements DuplicateChecker so
the service layer never knows Redis exists.
"""
from __future__ import annotations


class RedisDuplicateChecker:
    def __init__(self, redis_client, window_seconds: int = 3600):
        self._redis = redis_client
        self._window = window_seconds

    def seen_recently(self, application_id: str) -> bool:
        return self._redis.exists(f"rasheed:seen:{application_id}") == 1

    def mark_seen(self, application_id: str) -> None:
        self._redis.set(f"rasheed:seen:{application_id}", "1", ex=self._window)