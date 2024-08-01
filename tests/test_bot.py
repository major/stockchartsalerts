"""Tests for the bot."""

from unittest import mock

import freezegun

from stockchartsalerts import bot

SAMPLE_ALERTS = [
    {"alert": "There are no alerts today", "newalert": "yes", "bearish": "", "lastfired": "1 Aug 2024, 8:11 AM ET"},
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

    alerts = bot.get_alerts()
    assert len(alerts) == 6


def test_get_emoji():
    """Verify that we get the correct emoji."""
    assert bot.get_emoji({"bearish": "yes"}) == "🔴"
    assert bot.get_emoji({"bearish": "no"}) == "💚"


def test_send_alert_to_discord():
    """Verify that we send the alert to Discord."""
    with mock.patch("stockchartsalerts.bot.DiscordWebhook") as mock_discord:
        bot.send_alert_to_discord({
            "alert": "Test alert",
            "bearish": "no",
            "lastfired": "31 Jul 2024, 12:33pm",
            "symbol": "$COMPQ",
        })
        mock_discord.assert_called_once_with(
            url=bot.DISCORD_WEBHOOK,
            rate_limit_retry=True,
            username="$COMPQ",
            avatar_url="https://emojiguide.org/images/emoji/1/8z8e40kucdd1.png",
            content="💚  Test alert [📈](https://stockcharts.com/h-sc/ui?s=$COMPQ)",
        )
        mock_discord.return_value.execute.assert_called_once()
