"""Validated local settings. Credentials never belong in agent messages."""

import re
from decimal import Decimal
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

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


class DataSettings(BaseSettings):
    """Local operator commands need database access, not provider credentials."""

    model_config = Settings.model_config
    dashscope_api_key: SecretStr | None = Field(
        default=None, validation_alias="DASHSCOPE_API_KEY", repr=False
    )
    database_url: SecretStr = Field(validation_alias="DATABASE_URL", repr=False)
    telegram_owner_id: int = Field(gt=0)
    workspace_dir: Path = Path(".kestri/workspace")
    archive_retention_days: int = Field(default=90, ge=1, le=3650)
    evidence_retention_days: int = Field(default=30, ge=1, le=3650)
    log_retention_days: int = Field(default=30, ge=1, le=3650)
    backup_retention_days: int = Field(default=30, ge=1, le=3650)
    maintenance_interval_seconds: int = Field(default=3600, ge=60, le=86400)


class EmbeddingSettings(BaseSettings):
    """Independent Beijing embedding connection; no database/chat credentials needed."""

    model_config = Settings.model_config
    dashscope_api_key: SecretStr = Field(validation_alias="DASHSCOPE_API_KEY", repr=False)
    embedding_base_url: str
    embedding_model: Literal["text-embedding-v4"] = "text-embedding-v4"
    embedding_dimensions: Literal[64, 128, 256, 512, 768, 1024, 1536, 2048] = 1024
    embedding_timeout_seconds: float = Field(default=20, gt=0, le=60)
    embedding_evidence_dir: Path = Path(".kestri/evidence")

    @field_validator("embedding_dimensions", mode="before")
    @classmethod
    def parse_embedding_dimensions(cls, value: object) -> object:
        if isinstance(value, str) and value.isascii() and value.isdigit():
            return int(value)
        return value

    @field_validator("dashscope_api_key")
    @classmethod
    def validate_embedding_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("Configure DASHSCOPE_API_KEY locally")
        return value

    @field_validator("embedding_base_url")
    @classmethod
    def validate_embedding_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in {None, 443}
            or not re.fullmatch(
                r"[a-z0-9-]+\.cn-beijing\.maas\.aliyuncs\.com", parsed.hostname or ""
            )
            or parsed.path.rstrip("/") != "/compatible-mode/v1"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Use the official Beijing workspace embedding base URL")
        return value.rstrip("/")


class ResearchSettings(Settings, DataSettings):
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
    embedding_base_url: str | None = None
    embedding_model: Literal["text-embedding-v4"] = "text-embedding-v4"
    embedding_dimensions: Literal[1024] = 1024
    embedding_timeout_seconds: float = Field(default=20, gt=0, le=60)
    embedding_cny_per_million: Decimal = Field(default=Decimal("0.5"), gt=0, le=100)
    embedding_usd_per_cny: Decimal = Field(default=Decimal("0.15"), gt=0, le=1)
    embedding_conversion_version: str = Field(default="fixed-v1", min_length=1, max_length=64)
    memory_retrieval_timeout_seconds: float = Field(default=10, gt=0, le=30)
    memory_dense_min_similarity: float = Field(default=0.5, ge=-1, le=1)
    history_dense_min_similarity: float = Field(default=0.3, ge=-1, le=1)
    memory_limit: int = Field(default=64, ge=1, le=64)
    auto_memory_limit: int = Field(default=1000, ge=1, le=1000)
    memory_candidate_limit: int = Field(default=100, ge=1, le=100)
    memory_maintenance_budget_usd: Decimal = Field(default=Decimal("0.15"), gt=0, le=1)
    memory_maintenance_monthly_usd: Decimal = Field(default=Decimal("1.50"), gt=0, le=20)
    memory_context_limit: int = Field(default=8, ge=1, le=16)
    context_trigger_ratio: float = Field(default=0.70, ge=0.1, le=0.9)
    context_keep_messages: int = Field(default=12, ge=4, le=40)
    max_summary_calls: int = Field(default=2, ge=1, le=4)
    summary_max_chars: int = Field(default=4000, ge=500, le=8000)
    owner_timezone: str | None = None
    task_limit: int = Field(default=16, ge=1, le=64)
    background_queue_limit: int = Field(default=8, ge=1, le=32)
    scheduler_interval_seconds: float = Field(default=5, ge=1, le=60)

    @field_validator("embedding_base_url")
    @classmethod
    def validate_product_embedding_url(cls, value: str | None) -> str | None:
        return EmbeddingSettings.validate_embedding_url(value) if value is not None else None

    @field_validator("embedding_dimensions", mode="before")
    @classmethod
    def parse_product_dimensions(cls, value: object) -> object:
        return EmbeddingSettings.parse_embedding_dimensions(value)

    def embedding_config(self) -> EmbeddingSettings | None:
        if (
            self.dashscope_api_key is None
            or not self.dashscope_api_key.get_secret_value().strip()
            or self.embedding_base_url is None
        ):
            return None
        return EmbeddingSettings(
            _env_file=None,
            DASHSCOPE_API_KEY=self.dashscope_api_key,
            embedding_base_url=self.embedding_base_url,
            embedding_model=self.embedding_model,
            embedding_dimensions=self.embedding_dimensions,
            embedding_timeout_seconds=self.embedding_timeout_seconds,
        )

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
