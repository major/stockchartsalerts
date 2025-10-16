"""Tests for configuration settings."""

import pytest
from pydantic import ValidationError

from stockchartsalerts.config import Settings


def test_settings_defaults():
    """Test default configuration values."""
    settings = Settings()
    assert settings.minutes_between_runs == 5
    assert settings.discord_webhook == "missing"
    assert settings.sentry_dsn == ""
    assert settings.sentry_environment == "production"
    assert settings.git_commit == "unknown"
    assert settings.git_branch == "unknown"


def test_settings_from_env(monkeypatch):
    """Test loading settings from environment variables."""
    monkeypatch.setenv("MINUTES_BETWEEN_RUNS", "10")
    monkeypatch.setenv("DISCORD_WEBHOOK", "https://discord.com/api/webhooks/test")
    monkeypatch.setenv("SENTRY_DSN", "https://sentry.io/test")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "staging")
    monkeypatch.setenv("GIT_COMMIT", "abc123")
    monkeypatch.setenv("GIT_BRANCH", "main")

    settings = Settings()
    assert settings.minutes_between_runs == 10
    assert settings.discord_webhook == "https://discord.com/api/webhooks/test"
    assert settings.sentry_dsn == "https://sentry.io/test"
    assert settings.sentry_environment == "staging"
    assert settings.git_commit == "abc123"
    assert settings.git_branch == "main"


def test_minutes_between_runs_validation_too_low(monkeypatch):
    """Test that minutes_between_runs must be at least 1."""
    monkeypatch.setenv("MINUTES_BETWEEN_RUNS", "0")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "MINUTES_BETWEEN_RUNS" in str(
        exc_info.value
    ) or "greater than or equal" in str(exc_info.value)


def test_minutes_between_runs_validation_too_high(monkeypatch):
    """Test that minutes_between_runs cannot exceed 1440 (24 hours)."""
    monkeypatch.setenv("MINUTES_BETWEEN_RUNS", "1441")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "MINUTES_BETWEEN_RUNS" in str(exc_info.value) or "less than or equal" in str(
        exc_info.value
    )


def test_discord_webhook_validation_invalid_protocol(monkeypatch):
    """Test that discord_webhook must start with https://."""
    monkeypatch.setenv("DISCORD_WEBHOOK", "http://discord.com/api/webhooks/test")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "Discord webhook must start with https://" in str(exc_info.value)


def test_discord_webhook_allows_missing():
    """Test that 'missing' is allowed as a default for discord_webhook."""
    settings = Settings(discord_webhook="missing")
    assert settings.discord_webhook == "missing"


def test_discord_webhook_valid_https(monkeypatch):
    """Test that valid https:// webhooks are accepted."""
    monkeypatch.setenv("DISCORD_WEBHOOK", "https://discord.com/api/webhooks/12345")
    settings = Settings()
    assert settings.discord_webhook == "https://discord.com/api/webhooks/12345"


def test_minutes_between_runs_valid_range(monkeypatch):
    """Test valid minute ranges."""
    # Test minimum
    monkeypatch.setenv("MINUTES_BETWEEN_RUNS", "1")
    settings = Settings()
    assert settings.minutes_between_runs == 1

    # Test maximum
    monkeypatch.setenv("MINUTES_BETWEEN_RUNS", "1440")
    settings = Settings()
    assert settings.minutes_between_runs == 1440

    # Test middle value
    monkeypatch.setenv("MINUTES_BETWEEN_RUNS", "60")
    settings = Settings()
    assert settings.minutes_between_runs == 60
