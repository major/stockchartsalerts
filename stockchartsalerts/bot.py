"""Send alerts from stockcharts.com to other places."""

from datetime import datetime, time, timedelta

import httpx
import pytz
from dateutil import tz
from dateutil.parser import parse
from discord_webhook import DiscordWebhook

from stockchartsalerts.config import DISCORD_WEBHOOK, MINUTES_BETWEEN_RUNS


def get_alerts() -> list:
    """Get alerts from stockcharts.com."""
    headers = {
        "Referer": "https://stockcharts.com/freecharts/alertsummary.html",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0",
    }
    resp = httpx.get("https://stockcharts.com/j-sum/sum?cmd=alert", headers=headers)
    return list(resp.json())


def get_new_alerts() -> list:
    """Return only new alerts"""
    alerts = get_alerts()

    # Get the time of the previous run in Eastern time.
    eastern_time = pytz.timezone("America/New_York")
    previous_run = datetime.now(eastern_time) - timedelta(minutes=MINUTES_BETWEEN_RUNS)

    # We need the "lastfired" date parsed in the Eastern US time zone since that's
    # what stockcharts.com uses.
    default_date = datetime.combine(datetime.now(), time(0, tzinfo=tz.gettz("America/New_York")))

    return [x for x in alerts if parse(x["lastfired"], default=default_date) > previous_run]


def get_emoji(alert: dict) -> str:
    """Return the emoji for the alert."""
    return "🔴" if alert["bearish"] == "yes" else "💚"


def send_alert_to_discord(alert: dict) -> None:
    """Send a news item to a Discord webhook."""

    webhook = DiscordWebhook(
        url=DISCORD_WEBHOOK,
        rate_limit_retry=True,
        username=get_emoji(alert),
        content=alert["alert"],
    )

    webhook.execute()
