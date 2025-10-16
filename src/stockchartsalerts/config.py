"""Configuration settings."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Bot Configuration
    minutes_between_runs: int = Field(
        default=5,
        ge=1,  # Must be at least 1 minute
        le=1440,  # Max 24 hours
        description="Minutes to wait between alert checks",
        alias="MINUTES_BETWEEN_RUNS",
    )

    # Discord Configuration
    discord_webhook: str = Field(
        default="missing",
        min_length=1,
        description="Discord webhook URL for sending alerts",
        alias="DISCORD_WEBHOOK",
    )

    # Sentry Configuration
    sentry_dsn: str = Field(
        default="",
        description="Sentry DSN for error tracking",
        alias="SENTRY_DSN",
    )
    sentry_environment: str = Field(
        default="production",
        description="Sentry environment name",
        alias="SENTRY_ENVIRONMENT",
    )

    # Git Version Info (set at build time)
    git_commit: str = Field(
        default="unknown",
        description="Git commit hash",
        alias="GIT_COMMIT",
    )
    git_branch: str = Field(
        default="unknown",
        description="Git branch name",
        alias="GIT_BRANCH",
    )

    @field_validator("discord_webhook")
    @classmethod
    def validate_discord_webhook(cls, v: str) -> str:
        """Validate Discord webhook URL format."""
        if v != "missing" and not v.startswith("https://"):
            raise ValueError("Discord webhook must start with https://")
        return v


# Create a singleton instance
settings = Settings()

__all__ = [
    "Settings",
    "settings",
]
