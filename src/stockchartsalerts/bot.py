"""Send alerts from stockcharts.com to other places."""

from datetime import datetime, time, timedelta

import httpx
import pytz
from dateutil import tz
from dateutil.parser import parse
from discord_webhook import DiscordWebhook
from loguru import logger
from pydantic import ValidationError
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from stockchartsalerts.config import get_settings
from stockchartsalerts.models import Alert

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


def _normalize_alert(alert: Alert | dict) -> Alert | None:
    if isinstance(alert, Alert):
        return alert

    try:
        return Alert.model_validate(alert)
    except ValidationError as exc:
        logger.warning(f"⚠️  Skipping malformed alert payload: {exc}")
        return None


def get_alerts() -> list:
    """Get alerts from stockcharts.com, returns empty list on failure."""
    try:
        return _fetch_alerts()
    except (RetryError, ValueError) as exc:
        logger.exception(f"❌ Failed to fetch alerts after all retries: {exc}")
        return []  # Return empty list instead of crashing


def get_new_alerts() -> list[dict]:
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

    new_alerts: list[Alert] = []
    for alert in alerts:
        try:
            fired_at = parse(alert.lastfired, default=default_date)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "⚠️  Failed to parse lastfired for {}: {}",
                alert.symbol,
                exc,
            )
            continue

        if fired_at > previous_run:
            new_alerts.append(alert)

    return [alert.model_dump() for alert in new_alerts]


def filter_alerts(alerts: list[Alert | dict]) -> list[Alert]:
    """Filter out alerts that we don't want to send."""
    banned_strings = {"There are no alerts today"}
    filtered_alerts: list[Alert] = []

    for alert in alerts:
        normalized_alert = _normalize_alert(alert)
        if normalized_alert and normalized_alert.alert not in banned_strings:
            filtered_alerts.append(normalized_alert)

    return filtered_alerts


def get_emoji(alert: Alert | dict) -> str:
    """Return the emoji for the alert."""
    if isinstance(alert, dict):
        return "🔴" if alert.get("bearish") == "yes" else "💚"

    normalized_alert = _normalize_alert(alert)
    if not normalized_alert:
        return "💚"
    return "🔴" if normalized_alert.bearish == "yes" else "💚"


def format_discord_alert_text(alert_text: str) -> str:
    """Rewrite alert text for Discord when needed."""
    prefix = "Dow crosses above "
    if alert_text.startswith(prefix):
        level = alert_text.removeprefix(prefix)
        return f"THE DOW, THE DOW IS ABOVE {level}"
    return alert_text


def send_alert_to_discord(alert: Alert | dict) -> None:
    """Send a news item to Discord webhook(s)."""
    normalized_alert = _normalize_alert(alert)
    if not normalized_alert:
        logger.error("❌ Skipping Discord send for malformed alert payload")
        return

    logger.info(
        f"📤 Sending alert to Discord: {normalized_alert.alert} @ {normalized_alert.lastfired}"
    )

    # Get all configured webhook URLs
    webhook_urls = get_settings().get_discord_webhook_urls()
    logger.info(f"🔗 Sending to {len(webhook_urls)} webhook(s)")

    # Send to each webhook
    for i, webhook_url in enumerate(webhook_urls, 1):
        webhook = DiscordWebhook(
            url=webhook_url,
            rate_limit_retry=True,  # Library handles rate limiting automatically
            username=normalized_alert.symbol,
            avatar_url="https://emojiguide.org/images/emoji/1/8z8e40kucdd1.png",
            content=f"{get_emoji(normalized_alert)}  {format_discord_alert_text(normalized_alert.alert)}",
        )

        try:
            response = webhook.execute()
            if response.status_code >= 200 and response.status_code < 300:
                logger.info(
                    f"✅ Alert sent successfully to webhook {i}/{len(webhook_urls)}: {normalized_alert.symbol}"
                )
            else:
                logger.error(
                    f"❌ Discord webhook {i}/{len(webhook_urls)} failed: {normalized_alert.symbol} - "
                    f"Status {response.status_code}"
                )
        except Exception as e:
            logger.error(
                f"❌ Error sending alert to Discord webhook {i}/{len(webhook_urls)}: {normalized_alert.symbol} - {e}"
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
