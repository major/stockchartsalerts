"""Configuration settings."""

from loguru import logger
from pydantic import Field, model_validator
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

    # Discord Configuration - supports multiple webhooks
    discord_webhook_url: str | None = Field(
        None,
        description="Discord webhook URL (deprecated, use discord_webhook_urls)",
    )
    discord_webhook_urls: str | None = Field(
        None,
        description="Comma-separated Discord webhook URLs",
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

    @model_validator(mode="after")
    def validate_discord_config(self) -> "Settings":
        """
        🔍 Validate Discord webhook configuration.

        Ensures at least one Discord webhook URL is provided (either via
        discord_webhook_url or discord_webhook_urls). This maintains backward
        compatibility while supporting the new multi-webhook feature.

        Returns:
            Self with validated Discord configuration

        Raises:
            ValueError: If no Discord webhook URLs are configured
        """
        if not self.discord_webhook_url and not self.discord_webhook_urls:
            msg = (
                "At least one Discord webhook URL must be provided via "
                "DISCORD_WEBHOOK_URL or DISCORD_WEBHOOK_URLS"
            )
            raise ValueError(msg)
        return self

    def get_discord_webhook_urls(self) -> list[str]:
        """
        📋 Get list of Discord webhook URLs from configuration.

        Combines both the legacy single URL (discord_webhook_url) and the new
        comma-separated URLs (discord_webhook_urls) into a single list.

        Returns:
            List of Discord webhook URLs (deduplicated and stripped)

        Example:
            >>> settings.discord_webhook_url = "https://discord.com/api/webhooks/1"
            >>> settings.discord_webhook_urls = "https://discord.com/api/webhooks/2,https://discord.com/api/webhooks/3"
            >>> settings.get_discord_webhook_urls()
            ['https://discord.com/api/webhooks/1', 'https://discord.com/api/webhooks/2', 'https://discord.com/api/webhooks/3']
        """
        urls: list[str] = []

        # Add legacy single URL if present
        if self.discord_webhook_url:
            urls.append(self.discord_webhook_url.strip())

        # Add comma-separated URLs if present
        if self.discord_webhook_urls:
            # Split by comma and strip whitespace
            new_urls = [url.strip() for url in self.discord_webhook_urls.split(",")]
            # Filter out empty strings
            new_urls = [url for url in new_urls if url]
            urls.extend(new_urls)

        # Deduplicate while preserving order
        seen: set[str] = set()
        deduplicated: list[str] = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                deduplicated.append(url)

        return deduplicated

    def log_settings(self) -> None:
        """Log all configuration settings with sensitive values masked."""
        logger.info("⚙️  Configuration Settings:")
        logger.info(f"  📊 minutes_between_runs: {self.minutes_between_runs}")
        webhook_urls = self.get_discord_webhook_urls()
        logger.info(f"  🔔 discord_webhooks: {len(webhook_urls)} configured")
        for i, url in enumerate(webhook_urls, 1):
            # Truncate webhook URLs for security
            logger.info(f"     {i}. {url[:50]}...")
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
