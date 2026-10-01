"""Validated local settings. Credentials never belong in agent messages."""

from decimal import Decimal
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


class TelegramCredentials(BaseSettings):
    """Onboarding needs only a bot token, not research configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    telegram_bot_token: SecretStr = Field(validation_alias="TELEGRAM_BOT_TOKEN", repr=False)

    @field_validator("telegram_bot_token")
    @classmethod
    def validate_token(cls, value: SecretStr) -> SecretStr:
        import re

        if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{20,}", value.get_secret_value()):
            raise ValueError("Configure a valid bot token locally")
        return value


class ResearchSettings(Settings):
    """M1 configuration: explicit owner, durable local state, bounded providers."""

    telegram_bot_token: SecretStr = Field(validation_alias="TELEGRAM_BOT_TOKEN", repr=False)
    tavily_api_key: SecretStr = Field(validation_alias="TAVILY_API_KEY", repr=False)
    database_url: SecretStr = Field(validation_alias="DATABASE_URL", repr=False)
    telegram_owner_id: int = Field(gt=0)
    max_model_calls: int = Field(default=8, ge=1, le=20)
    max_tool_calls: int = Field(default=8, ge=1, le=20)
    run_timeout_seconds: float = Field(default=120, gt=0, le=300)
    request_timeout_seconds: float = Field(default=30, gt=0, le=120)
    max_output_tokens: int = Field(default=4096, ge=64, le=8192)
    input_token_budget: int = Field(default=128_000, ge=4096, le=256_000)
    tool_output_chars: int = Field(default=12_000, ge=2000, le=32_000)
    max_reply_chars: int = Field(default=12_000, ge=1000, le=16_000)
    workspace_dir: Path = Path(".kestri/workspace")
    url_dns_mode: Literal["system", "cloudflare"] = "system"
    queue_limit: int = Field(default=8, ge=1, le=32)
    monthly_budget_usd: Decimal = Field(default=Decimal("20"), gt=0, le=1000)
    run_budget_usd: Decimal = Field(default=Decimal("0.50"), gt=0, le=20)
    input_usd_per_million: Decimal = Field(default=Decimal("0.30"), gt=0, le=100)
    output_usd_per_million: Decimal = Field(default=Decimal("1.20"), gt=0, le=100)
    search_credit_usd: Decimal = Field(default=Decimal("0.008"), gt=0, le=1)
    owner_timezone: str | None = None
    task_limit: int = Field(default=16, ge=1, le=64)
    background_queue_limit: int = Field(default=8, ge=1, le=32)
    scheduler_interval_seconds: float = Field(default=5, ge=1, le=60)

    @field_validator("owner_timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        from zoneinfo import ZoneInfo

        if value is not None:
            ZoneInfo(value)
        return value

    @field_validator("telegram_bot_token")
    @classmethod
    def require_token(cls, value: SecretStr) -> SecretStr:
        return TelegramCredentials.validate_token(value)

    @field_validator("tavily_api_key", "database_url")
    @classmethod
    def require_secret(cls, value: SecretStr) -> SecretStr:
        return Settings.require_nonempty_key(value)
