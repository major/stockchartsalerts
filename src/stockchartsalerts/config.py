"""Configuration settings."""

from loguru import logger
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def mask_webhook_url(url: str) -> str:
    """Mask sensitive parts of a Discord webhook URL for logging.

    Args:
        url: The full webhook URL

    Returns:
        Masked URL showing only first/last few characters of sensitive parts

    Example:
        https://discord.com/api/webhooks/1234...6789/AbCd...7890
    """
    if url == "missing":
        return "missing ⚠️"

    if not url.startswith("https://"):
        return "invalid-format ⚠️"

    try:
        # Discord webhook format: https://discord.com/api/webhooks/{id}/{token}
        parts = url.split("/")
        if len(parts) < 7 or "webhooks" not in parts:
            return "invalid-webhook-format ⚠️"

        webhook_id = parts[-2]
        token = parts[-1]

        # Show first 4 and last 4 chars of ID and token
        masked_id = (
            f"{webhook_id[:4]}...{webhook_id[-4:]}" if len(webhook_id) > 8 else "***"
        )
        masked_token = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "***"

        return f"https://discord.com/api/webhooks/{masked_id}/{masked_token}"
    except Exception:
        return "error-parsing-url ⚠️"


def mask_sentry_dsn(dsn: str) -> str:
    """Mask sensitive parts of a Sentry DSN for logging.

    Args:
        dsn: The full Sentry DSN

    Returns:
        Masked DSN showing only non-sensitive parts

    Example:
        https://****@o123456.ingest.sentry.io/7890123
    """
    if not dsn:
        return "(empty)"

    if not dsn.startswith("https://"):
        return "invalid-format ⚠️"

    try:
        # Sentry DSN format: https://{key}@{org}.ingest.sentry.io/{project}
        if "@" in dsn:
            protocol_and_key, rest = dsn.split("@", 1)
            # Show first 4 chars of key
            key_part = (
                protocol_and_key.split("//", 1)[1] if "//" in protocol_and_key else ""
            )
            masked_key = f"{key_part[:4]}****" if len(key_part) > 4 else "****"
            return f"https://{masked_key}@{rest}"
        return "invalid-dsn-format ⚠️"
    except Exception:
        return "error-parsing-dsn ⚠️"


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

    def log_settings(self) -> None:
        """Log all configuration settings with sensitive values masked."""
        logger.info("⚙️  Configuration Settings:")
        logger.info(f"  📊 minutes_between_runs: {self.minutes_between_runs}")
        logger.info(f"  🔔 discord_webhook: {mask_webhook_url(self.discord_webhook)}")
        logger.info(f"  🐛 sentry_dsn: {self.sentry_dsn}")
        logger.info(f"  🌍 sentry_environment: {self.sentry_environment}")
        logger.info(f"  📝 git_commit: {self.git_commit}")
        logger.info(f"  🌿 git_branch: {self.git_branch}")


# Create a singleton instance
settings = Settings()

# Log all settings at startup with sensitive values masked
settings.log_settings()

__all__ = [
    "Settings",
    "settings",
    "mask_webhook_url",
    "mask_sentry_dsn",
]
