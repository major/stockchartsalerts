"""Behavior scenarios for environment-based application configuration."""

import pytest

from stockchartsalerts import Settings, load_settings


def test_webhook_configuration_deduplicates_urls_and_uses_defaults() -> None:
    """Webhook entries are trimmed and deduplicated, with runtime defaults."""
    settings = load_settings({"DISCORD_WEBHOOK_URLS": " https://one ,https://two,https://one ,, "})

    assert settings == Settings(
        webhook_urls=("https://one", "https://two"),
        minutes_between_runs=5,
        git_commit="unknown",
        git_branch="unknown",
        log_level="info",
    )


def test_build_labels_and_log_level_are_normalized() -> None:
    """Optional labels are trimmed and recognized log levels are lowercased."""
    settings = load_settings(
        {
            "DISCORD_WEBHOOK_URLS": "anything",
            "GIT_COMMIT": " abc ",
            "GIT_BRANCH": " main ",
            "LOG_LEVEL": " WARN ",
        }
    )

    assert settings == Settings(
        webhook_urls=("anything",),
        minutes_between_runs=5,
        git_commit="abc",
        git_branch="main",
        log_level="warn",
    )


@pytest.mark.parametrize(("raw_minutes", "expected"), [("1", 1), ("+001", 1), ("1440", 1440)])
def test_polling_interval_accepts_integer_text_at_inclusive_bounds(
    raw_minutes: str,
    expected: int,
) -> None:
    """Polling intervals accept integer text from one through one day."""
    settings = load_settings(
        {
            "DISCORD_WEBHOOK_URLS": "https://one",
            "MINUTES_BETWEEN_RUNS": raw_minutes,
        }
    )

    assert settings.minutes_between_runs == expected


@pytest.mark.parametrize("raw_minutes", ["0", "-0", "1441", "", " 5", "5 ", "1_0", "1.5"])
def test_polling_interval_rejects_invalid_or_padded_integer_text(raw_minutes: str) -> None:
    """Out-of-range, whitespace-padded, or non-integer intervals are rejected."""
    with pytest.raises(ValueError):
        load_settings(
            {
                "DISCORD_WEBHOOK_URLS": "https://one",
                "MINUTES_BETWEEN_RUNS": raw_minutes,
            }
        )


@pytest.mark.parametrize("webhooks", ["", "  ", ", ,", None])
def test_webhook_configuration_requires_nonempty_plural_urls(webhooks: str | None) -> None:
    """An empty plural setting or singular-only setting is not accepted."""
    env: dict[str, str] = {"DISCORD_WEBHOOK_URL": "https://singular"}
    if webhooks is not None:
        env["DISCORD_WEBHOOK_URLS"] = webhooks

    with pytest.raises(ValueError, match="DISCORD_WEBHOOK_URLS"):
        load_settings(env)


@pytest.mark.parametrize(
    ("raw_level", "expected_level"),
    [
        ("DEBUG", "debug"),
        (" info ", "info"),
        ("Warn", "warn"),
        ("ERROR", "error"),
        ("warning", "info"),
        ("trace", "info"),
    ],
)
def test_log_level_normalization_accepts_known_levels_and_defaults_unknown_values(
    raw_level: str,
    expected_level: str,
) -> None:
    """Known levels are normalized and unsupported names fall back to info."""
    settings = load_settings({"DISCORD_WEBHOOK_URLS": "https://one", "LOG_LEVEL": raw_level})

    assert settings.log_level == expected_level
