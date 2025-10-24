"""Tests for the config module."""

import pytest

from stockchartsalerts.config import Settings


def test_get_discord_webhook_urls_single_legacy():
    """Test get_discord_webhook_urls with only legacy discord_webhook_url."""
    settings = Settings(
        discord_webhook_url="https://discord.com/api/webhooks/123/abc",
        _env_file=None,
    )
    urls = settings.get_discord_webhook_urls()
    assert urls == ["https://discord.com/api/webhooks/123/abc"]


def test_get_discord_webhook_urls_single_new():
    """Test get_discord_webhook_urls with only new discord_webhook_urls."""
    settings = Settings(
        discord_webhook_urls="https://discord.com/api/webhooks/123/abc",
        _env_file=None,
    )
    urls = settings.get_discord_webhook_urls()
    assert urls == ["https://discord.com/api/webhooks/123/abc"]


def test_get_discord_webhook_urls_multiple():
    """Test get_discord_webhook_urls with multiple comma-separated URLs."""
    settings = Settings(
        discord_webhook_urls="https://discord.com/api/webhooks/1/abc,https://discord.com/api/webhooks/2/def,https://discord.com/api/webhooks/3/ghi",
        _env_file=None,
    )
    urls = settings.get_discord_webhook_urls()
    assert urls == [
        "https://discord.com/api/webhooks/1/abc",
        "https://discord.com/api/webhooks/2/def",
        "https://discord.com/api/webhooks/3/ghi",
    ]


def test_get_discord_webhook_urls_multiple_with_spaces():
    """Test get_discord_webhook_urls handles whitespace around commas."""
    settings = Settings(
        discord_webhook_urls="https://discord.com/api/webhooks/1/abc , https://discord.com/api/webhooks/2/def  ,  https://discord.com/api/webhooks/3/ghi",
        _env_file=None,
    )
    urls = settings.get_discord_webhook_urls()
    assert urls == [
        "https://discord.com/api/webhooks/1/abc",
        "https://discord.com/api/webhooks/2/def",
        "https://discord.com/api/webhooks/3/ghi",
    ]


def test_get_discord_webhook_urls_combined():
    """Test get_discord_webhook_urls combines legacy and new URLs."""
    settings = Settings(
        discord_webhook_url="https://discord.com/api/webhooks/legacy/xyz",
        discord_webhook_urls="https://discord.com/api/webhooks/1/abc,https://discord.com/api/webhooks/2/def",
        _env_file=None,
    )
    urls = settings.get_discord_webhook_urls()
    assert urls == [
        "https://discord.com/api/webhooks/legacy/xyz",
        "https://discord.com/api/webhooks/1/abc",
        "https://discord.com/api/webhooks/2/def",
    ]


def test_get_discord_webhook_urls_deduplication():
    """Test get_discord_webhook_urls removes duplicate URLs."""
    settings = Settings(
        discord_webhook_url="https://discord.com/api/webhooks/123/abc",
        discord_webhook_urls="https://discord.com/api/webhooks/123/abc,https://discord.com/api/webhooks/456/def",
        _env_file=None,
    )
    urls = settings.get_discord_webhook_urls()
    assert urls == [
        "https://discord.com/api/webhooks/123/abc",
        "https://discord.com/api/webhooks/456/def",
    ]


def test_get_discord_webhook_urls_empty_strings():
    """Test get_discord_webhook_urls filters out empty strings."""
    settings = Settings(
        discord_webhook_urls="https://discord.com/api/webhooks/1/abc,,https://discord.com/api/webhooks/2/def,  ,https://discord.com/api/webhooks/3/ghi",
        _env_file=None,
    )
    urls = settings.get_discord_webhook_urls()
    assert urls == [
        "https://discord.com/api/webhooks/1/abc",
        "https://discord.com/api/webhooks/2/def",
        "https://discord.com/api/webhooks/3/ghi",
    ]


def test_validate_discord_config_requires_at_least_one():
    """Test that at least one Discord webhook URL is required."""
    with pytest.raises(ValueError, match="At least one Discord webhook URL"):
        Settings(_env_file=None)


def test_validate_discord_config_accepts_legacy_only():
    """Test that legacy discord_webhook_url alone is sufficient."""
    settings = Settings(
        discord_webhook_url="https://discord.com/api/webhooks/123/abc",
        _env_file=None,
    )
    assert settings.discord_webhook_url == "https://discord.com/api/webhooks/123/abc"


def test_validate_discord_config_accepts_new_only():
    """Test that new discord_webhook_urls alone is sufficient."""
    settings = Settings(
        discord_webhook_urls="https://discord.com/api/webhooks/123/abc",
        _env_file=None,
    )
    assert settings.discord_webhook_urls == "https://discord.com/api/webhooks/123/abc"
