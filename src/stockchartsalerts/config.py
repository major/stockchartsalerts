"""Configuration settings."""

from pydantic import Field
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
        description="Minutes to wait between alert checks",
        alias="MINUTES_BETWEEN_RUNS",
    )

    # Discord Configuration
    discord_webhook: str = Field(
        default="missing",
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


# Create a singleton instance
settings = Settings()

# Export individual settings for backward compatibility
MINUTES_BETWEEN_RUNS: int = settings.minutes_between_runs
DISCORD_WEBHOOK: str = settings.discord_webhook
SENTRY_DSN: str = settings.sentry_dsn
SENTRY_ENVIRONMENT: str = settings.sentry_environment
GIT_COMMIT: str = settings.git_commit
GIT_BRANCH: str = settings.git_branch

__all__ = [
    "Settings",
    "settings",
    "MINUTES_BETWEEN_RUNS",
    "DISCORD_WEBHOOK",
    "SENTRY_DSN",
    "SENTRY_ENVIRONMENT",
    "GIT_COMMIT",
    "GIT_BRANCH",
]
