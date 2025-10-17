"""Configuration settings."""

from loguru import logger
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
        ge=1,  # Must be at least 1 minute
        le=1440,  # Max 24 hours
        description="Minutes to wait between alert checks",
    )

    # Discord Configuration
    discord_webhook_url: str = Field(
        min_length=1,
        description="Discord webhook URL for sending alerts",
    )

    # Sentry Configuration
    sentry_dsn: str = Field(
        default="",
        description="Sentry DSN for error tracking",
    )
    sentry_environment: str = Field(
        default="production",
        description="Sentry environment name",
    )

    # Git Version Info (set at build time)
    git_commit: str = Field(
        default="unknown",
        description="Git commit hash",
    )
    git_branch: str = Field(
        default="unknown",
        description="Git branch name",
    )

    def log_settings(self) -> None:
        """Log all configuration settings with sensitive values masked."""
        logger.info("⚙️  Configuration Settings:")
        logger.info(f"  📊 minutes_between_runs: {self.minutes_between_runs}")
        logger.info(f"  🔔 discord_webhook: {self.discord_webhook_url}")
        logger.info(f"  🐛 sentry_dsn: {self.sentry_dsn}")
        logger.info(f"  🌍 sentry_environment: {self.sentry_environment}")
        logger.info(f"  📝 git_commit: {self.git_commit}")
        logger.info(f"  🌿 git_branch: {self.git_branch}")


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the settings singleton.

    Returns:
        Settings instance with configuration loaded from environment variables
    """
    global _settings
    if _settings is None:
        _settings = Settings()  # pyright: ignore[reportCallIssue]
        # Log all settings at startup with sensitive values masked
        _settings.log_settings()
    return _settings


__all__ = [
    "Settings",
    "get_settings",
]
