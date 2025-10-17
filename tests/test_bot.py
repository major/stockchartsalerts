"""Tests for the bot."""

from unittest import mock

import freezegun
import pytest
from tenacity import wait_none

from stockchartsalerts import bot
from stockchartsalerts.config import get_settings


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """Mock settings for all tests by setting required environment variables."""
    monkeypatch.setenv("DISCORD_WEBHOOK", "https://discord.com/api/webhooks/123/abc")
    # Reset the settings singleton between tests
    import stockchartsalerts.config

    stockchartsalerts.config._settings = None
    yield
    # Clean up after test
    stockchartsalerts.config._settings = None


SAMPLE_ALERTS = [
    {
        "alert": "There are no alerts today",
        "newalert": "yes",
        "bearish": "",
        "lastfired": "1 Aug 2024, 8:11 AM ET",
    },
    {
        "symbol": "$BPSPX",
        "alertpaused": "no",
        "bearish": "no",
        "notes": "",
        "alert": "S&P 500 Bullish Percent Index crosses above 70",
        "lastfired": "31 Jul 2024, 2:31pm",
        "newalert": "yes",
        "type": "a",
        "recid": "701",
    },
    {
        "symbol": "$BPINFO",
        "alertpaused": "no",
        "bearish": "yes",
        "notes": "",
        "alert": "Technology Sector Bullish Percent Index crosses below 50",
        "lastfired": "31 Jul 2024, 12:55pm",
        "newalert": "yes",
        "type": "a",
        "recid": "1739",
    },
    {
        "symbol": "$INDU",
        "alertpaused": "no",
        "bearish": "no",
        "notes": "",
        "alert": "Dow crosses above 41000",
        "lastfired": "31 Jul 2024, 12:33pm",
        "newalert": "yes",
        "type": "a",
        "recid": "452083",
    },
    {
        "symbol": "$COMPQ",
        "alertpaused": "no",
        "bearish": "yes",
        "notes": "",
        "alert": "Nasdaq crosses below 17200",
        "lastfired": "31 Jul 2024, 11:47am",
        "newalert": "yes",
        "type": "a",
        "recid": "450121",
    },
    {
        "symbol": "$COMPQ",
        "alertpaused": "no",
        "bearish": "yes",
        "notes": "",
        "alert": "Nasdaq crosses below 17300",
        "lastfired": "31 Jul 2024, 11:47am",
        "newalert": "yes",
        "type": "a",
        "recid": "450208",
    },
]


@freezegun.freeze_time("2024-07-31 16:00:00")
@mock.patch("stockchartsalerts.bot.get_alerts", return_value=SAMPLE_ALERTS)
def test_get_new_alerts(mock_get_alerts):
    """Verify that we only get new alerts."""
    alerts = bot.get_new_alerts()
    assert len(alerts) == 3
    assert [x["symbol"] for x in alerts] == ["$BPSPX", "$BPINFO", "$INDU"]


@mock.patch("stockchartsalerts.bot.get_alerts", return_value=SAMPLE_ALERTS)
def test_filter_alerts(mock_get_alerts):
    """Verify the alert filter works."""
    alerts = bot.get_alerts()
    alerts = bot.filter_alerts(alerts)
    assert len(alerts) == 5


def test_get_alerts(httpx_mock):
    """Verify that we get alerts."""
    httpx_mock.add_response(
        url="https://stockcharts.com/j-sum/sum?cmd=alert",
        json=SAMPLE_ALERTS,
    )

    alerts = bot.get_alerts()
    assert alerts == SAMPLE_ALERTS

    httpx_mock.add_response(
        url="https://stockcharts.com/j-sum/sum?cmd=alert",
        json=SAMPLE_ALERTS,
    )

    alerts = bot.get_alerts()
    assert len(alerts) == 6


def test_get_emoji():
    """Verify that we get the correct emoji."""
    assert bot.get_emoji({"bearish": "yes"}) == "🔴"
    assert bot.get_emoji({"bearish": "no"}) == "💚"


def test_send_alert_to_discord():
    """Verify that we send the alert to Discord."""
    with mock.patch("stockchartsalerts.bot.DiscordWebhook") as mock_discord:
        # Mock the response to have a successful status code
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_discord.return_value.execute.return_value = mock_response

        bot.send_alert_to_discord({
            "alert": "Test alert",
            "bearish": "no",
            "lastfired": "31 Jul 2024, 12:33pm",
            "symbol": "$COMPQ",
        })
        mock_discord.assert_called_once_with(
            url=get_settings().discord_webhook,
            rate_limit_retry=True,
            username="$COMPQ",
            avatar_url="https://emojiguide.org/images/emoji/1/8z8e40kucdd1.png",
            content="💚  Test alert",
        )
        mock_discord.return_value.execute.assert_called_once()


def test_get_alerts_http_error_retries_then_returns_empty(httpx_mock):
    """Test that get_alerts retries on HTTP errors and returns empty list."""
    # Mock 3 failures
    for _ in range(3):
        httpx_mock.add_response(
            url="https://stockcharts.com/j-sum/sum?cmd=alert",
            status_code=500,
        )

    # Patch tenacity's wait to make test instant
    with mock.patch.object(bot._fetch_alerts.retry, "wait", wait_none()):
        alerts = bot.get_alerts()

    assert alerts == []  # Should return empty list after retries


def test_get_alerts_timeout_retries_then_returns_empty(httpx_mock):
    """Test that get_alerts retries on timeout and returns empty list."""
    import httpx

    # Mock 3 timeouts
    httpx_mock.add_exception(httpx.TimeoutException("Connection timeout"))
    httpx_mock.add_exception(httpx.TimeoutException("Connection timeout"))
    httpx_mock.add_exception(httpx.TimeoutException("Connection timeout"))

    # Patch tenacity's wait to make test instant
    with mock.patch.object(bot._fetch_alerts.retry, "wait", wait_none()):
        alerts = bot.get_alerts()

    assert alerts == []  # Should return empty list after retries


def test_get_alerts_network_error_retries_then_returns_empty(httpx_mock):
    """Test that get_alerts retries on network errors and returns empty list."""
    import httpx

    # Mock 3 network errors
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

    # Patch tenacity's wait to make test instant
    with mock.patch.object(bot._fetch_alerts.retry, "wait", wait_none()):
        alerts = bot.get_alerts()

    assert alerts == []  # Should return empty list after retries


def test_get_alerts_succeeds_after_retry(httpx_mock):
    """Test that get_alerts succeeds after initial failures."""
    import httpx

    # First two requests fail, third succeeds
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
    httpx_mock.add_exception(httpx.TimeoutException("Timeout"))
    httpx_mock.add_response(
        url="https://stockcharts.com/j-sum/sum?cmd=alert",
        json=SAMPLE_ALERTS,
    )

    # Patch tenacity's wait to make test instant
    with mock.patch.object(bot._fetch_alerts.retry, "wait", wait_none()):
        alerts = bot.get_alerts()

    assert alerts == SAMPLE_ALERTS  # Should succeed on third try


def test_send_alert_to_discord_error_status_code():
    """Test Discord webhook with error status code."""
    with mock.patch("stockchartsalerts.bot.DiscordWebhook") as mock_discord:
        # Mock error response
        mock_response = mock.MagicMock()
        mock_response.status_code = 400
        mock_discord.return_value.execute.return_value = mock_response

        # Should not raise an exception, just log the error
        bot.send_alert_to_discord({
            "alert": "Test alert",
            "bearish": "no",
            "lastfired": "31 Jul 2024, 12:33pm",
            "symbol": "$COMPQ",
        })

        # Verify webhook was called
        mock_discord.return_value.execute.assert_called_once()


def test_send_alert_to_discord_exception():
    """Test Discord webhook handles exceptions gracefully."""
    with mock.patch("stockchartsalerts.bot.DiscordWebhook") as mock_discord:
        # Mock exception
        mock_discord.return_value.execute.side_effect = Exception("Network error")

        # Should not raise an exception, just log the error
        bot.send_alert_to_discord({
            "alert": "Test alert",
            "bearish": "no",
            "lastfired": "31 Jul 2024, 12:33pm",
            "symbol": "$COMPQ",
        })

        # Verify webhook was called
        mock_discord.return_value.execute.assert_called_once()
