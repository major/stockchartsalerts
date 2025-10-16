"""Send alerts from stockcharts.com to other places."""

import logging
from datetime import datetime, time, timedelta
from time import sleep

import httpx
import pytz
from dateutil import tz
from dateutil.parser import parse
from discord_webhook import DiscordWebhook

from stockchartsalerts.config import DISCORD_WEBHOOK, MINUTES_BETWEEN_RUNS

log = logging.getLogger(__name__)

# Constants for retry logic
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
HTTP_TIMEOUT = 30.0  # seconds


def get_alerts() -> list:
    """Get alerts from stockcharts.com with retry logic."""
    headers = {
        "Referer": "https://stockcharts.com/freecharts/alertsummary.html",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0",
    }

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = httpx.get(
                "https://stockcharts.com/j-sum/sum?cmd=alert",
                headers=headers,
                timeout=HTTP_TIMEOUT,
                follow_redirects=True,
            )
            resp.raise_for_status()
            return list(resp.json())
        except httpx.HTTPStatusError as e:
            last_error = e
            log.warning(
                f"HTTP error fetching alerts (attempt {attempt}/{MAX_RETRIES}): "
                f"Status {e.response.status_code}"
            )
        except httpx.TimeoutException as e:
            last_error = e
            log.warning(
                f"Timeout fetching alerts (attempt {attempt}/{MAX_RETRIES}): {e}"
            )
        except httpx.RequestError as e:
            last_error = e
            log.warning(
                f"Network error fetching alerts (attempt {attempt}/{MAX_RETRIES}): {e}"
            )
        except Exception as e:
            last_error = e
            log.warning(
                f"Unexpected error fetching alerts (attempt {attempt}/{MAX_RETRIES}): {e}"
            )

        # Don't sleep after the last attempt
        if attempt < MAX_RETRIES:
            sleep(RETRY_DELAY * attempt)  # Exponential backoff

    # All retries failed
    log.error(f"Failed to fetch alerts after {MAX_RETRIES} attempts: {last_error}")
    return []  # Return empty list instead of crashing


def get_new_alerts() -> list:
    """Return only new alerts"""
    alerts = get_alerts()
    alerts = filter_alerts(alerts)

    # Get the time of the previous run in Eastern time.
    eastern_time = pytz.timezone("America/New_York")
    previous_run = datetime.now(eastern_time) - timedelta(minutes=MINUTES_BETWEEN_RUNS)

    # We need the "lastfired" date parsed in the Eastern US time zone since that's
    # what stockcharts.com uses.
    default_date = datetime.combine(
        datetime.now(), time(0, tzinfo=tz.gettz("America/New_York"))
    )

    return [
        x for x in alerts if parse(x["lastfired"], default=default_date) > previous_run
    ]


def filter_alerts(alerts: list) -> list:
    """Filter out alerts that we don't want to send."""
    banned_strings = ["There are no alerts today"]
    return [x for x in alerts if x["alert"] not in banned_strings]


def get_emoji(alert: dict) -> str:
    """Return the emoji for the alert."""
    return "🔴" if alert["bearish"] == "yes" else "💚"


def send_alert_to_discord(alert: dict) -> None:
    """Send a news item to a Discord webhook."""
    log.info(f"Sending alert to Discord: {alert['alert']} @ {alert['lastfired']}")

    webhook = DiscordWebhook(
        url=DISCORD_WEBHOOK,
        rate_limit_retry=True,  # Library handles rate limiting automatically
        username=alert["symbol"],
        avatar_url="https://emojiguide.org/images/emoji/1/8z8e40kucdd1.png",
        content=f"{get_emoji(alert)}  {alert['alert']}",
    )

    try:
        response = webhook.execute()
        if response.status_code >= 200 and response.status_code < 300:
            log.info(f"✅ Alert sent successfully: {alert['symbol']}")
        else:
            log.error(
                f"❌ Discord webhook failed: {alert['symbol']} - "
                f"Status {response.status_code}"
            )
    except Exception as e:
        log.error(f"❌ Error sending alert to Discord: {alert['symbol']} - {e}")
