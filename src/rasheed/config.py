"""Typed, fail-fast configuration. One place to read every
environment variable - never scatter os.environ[...] across the codebase.
"""
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RASHEED_",
        env_file=".env",
        extra="forbid",  # unknown RASHEED_* = crash, not a silent default
    )

    model_path: Path = Field(
        default=Path("models/rasheed_lr_v1.joblib"),
        description="Path to the joblib model bundle",
    )
    accept_threshold: float = Field(0.75, ge=0.0, le=1.0)
    reject_threshold: float = Field(0.35, ge=0.0, le=1.0)
    min_gpa_for_auto_accept: float = Field(2.0, ge=0.0, le=5.0)
    log_level: str = "INFO"
    redis_url: SecretStr | None = None
    git_sha: str = "dev"  # injected by CI as RASHEED_GIT_SHA

    @field_validator("model_path")
    @classmethod
    def model_file_must_exist(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(f"model artefact not found: {v}")
        return v