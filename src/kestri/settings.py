"""Validated local settings. Credentials never belong in agent messages."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KESTRI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    deepseek_api_key: SecretStr = Field(validation_alias="DEEPSEEK_API_KEY", repr=False)
    model: str = Field(default="deepseek-flash", min_length=1, max_length=100)
    thinking_mode: Literal["enabled", "disabled"] = "disabled"
    max_model_calls: int = Field(default=4, ge=1, le=20)
    max_tool_calls: int = Field(default=4, ge=1, le=20)
    run_timeout_seconds: float = Field(default=60, gt=0, le=300)
    request_timeout_seconds: float = Field(default=20, gt=0, le=120)
    max_output_tokens: int = Field(default=1024, ge=64, le=8192)
    evidence_dir: Path = Path(".kestri/evidence")

    @field_validator("deepseek_api_key")
    @classmethod
    def require_nonempty_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("DEEPSEEK_API_KEY must be configured locally")
        return value
