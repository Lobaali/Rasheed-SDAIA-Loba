"""Typed, fail-fast configuration. One place to read every
environment variable - never scatter os.environ[...] across the codebase.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RASHEED_", env_file=".env")

    model_path: str = "models/rasheed_lr_v1.joblib"
    accept_threshold: float = 0.75
    reject_threshold: float = 0.35
    min_gpa_for_auto_accept: float = 2.0
    log_level: str = "INFO"
    redis_url: str | None = None