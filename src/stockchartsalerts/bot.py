"""Send alerts from stockcharts.com to other places."""

from datetime import datetime, time, timedelta

import httpx
import pytz
from dateutil import tz
from dateutil.parser import parse
from discord_webhook import DiscordWebhook
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from stockchartsalerts.config import get_settings

# HTTP timeout constant
HTTP_TIMEOUT = 30.0  # seconds

# MEMORY LEAK FIX: Create a persistent httpx client that is reused across all requests.
# Previously, httpx.get() was creating a new client on every call (every 5 minutes),
# which accumulated unclosed connection pools, TCP connections, and buffers.
# This caused OOMKilled errors in Kubernetes after running for hours/days.
# Using a persistent client with connection pooling prevents this memory leak.
_http_client = httpx.Client(
    timeout=HTTP_TIMEOUT,
    follow_redirects=True,
    # Configure connection pool limits to prevent resource exhaustion
    limits=httpx.Limits(
        max_keepalive_connections=5,  # Keep only 5 persistent connections
        max_connections=10,  # Max 10 total connections
        keepalive_expiry=30.0,  # Close idle connections after 30s
    ),
)


def _log_retry(retry_state):
    """Log retry attempts."""
    exception = retry_state.outcome.exception() if retry_state.outcome else "Unknown"
    logger.warning(
        f"⚠️  Retrying get_alerts (attempt {retry_state.attempt_number}/3) after error: {exception}"
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    before_sleep=_log_retry,
)
def _fetch_alerts() -> list:
    """Fetch alerts with automatic retry - internal function."""
    headers = {
        "Referer": "https://stockcharts.com/freecharts/alertsummary.html",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0",
    }

    # Use the persistent client instead of httpx.get() to prevent memory leaks
    resp = _http_client.get(
        "https://stockcharts.com/j-sum/sum?cmd=alert",
        headers=headers,
    )
    resp.raise_for_status()
    return list(resp.json())


def get_alerts() -> list:
    """Get alerts from stockcharts.com, returns empty list on failure."""
    try:
        return _fetch_alerts()
    except Exception as e:
        logger.error(f"❌ Failed to fetch alerts after all retries: {e}")
        return []  # Return empty list instead of crashing


def get_new_alerts() -> list:
    """Return only new alerts"""
    alerts = get_alerts()
    alerts = filter_alerts(alerts)

    # Get the time of the previous run in Eastern time.
    eastern_time = pytz.timezone("America/New_York")
    previous_run = datetime.now(eastern_time) - timedelta(
        minutes=get_settings().minutes_between_runs
    )

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
    """Send a news item to Discord webhook(s)."""
    logger.info(f"📤 Sending alert to Discord: {alert['alert']} @ {alert['lastfired']}")

    # Get all configured webhook URLs
    webhook_urls = get_settings().get_discord_webhook_urls()
    logger.info(f"🔗 Sending to {len(webhook_urls)} webhook(s)")

    # Send to each webhook
    for i, webhook_url in enumerate(webhook_urls, 1):
        webhook = DiscordWebhook(
            url=webhook_url,
            rate_limit_retry=True,  # Library handles rate limiting automatically
            username=alert["symbol"],
            avatar_url="https://emojiguide.org/images/emoji/1/8z8e40kucdd1.png",
            content=f"{get_emoji(alert)}  {alert['alert']}",
        )

        try:
            response = webhook.execute()
            if response.status_code >= 200 and response.status_code < 300:
                logger.info(
                    f"✅ Alert sent successfully to webhook {i}/{len(webhook_urls)}: {alert['symbol']}"
                )
            else:
                logger.error(
                    f"❌ Discord webhook {i}/{len(webhook_urls)} failed: {alert['symbol']} - "
                    f"Status {response.status_code}"
                )
        except Exception as e:
            logger.error(
                f"❌ Error sending alert to Discord webhook {i}/{len(webhook_urls)}: {alert['symbol']} - {e}"
            )


def cleanup() -> None:
    """
    Clean up resources on shutdown.

    Properly closes the persistent HTTP client to release connection pools
    and prevent resource leaks. While less critical in containerized environments
    (OS cleans up on process exit), this ensures graceful shutdown.
    """
    logger.info("🧹 Cleaning up HTTP client...")
    _http_client.close()
