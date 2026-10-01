"""Polling and delivery orchestration for StockCharts alerts."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from stockchartsalerts import alerts, discord, stockcharts
from stockchartsalerts.config import Settings

logger = logging.getLogger(__name__)
_EASTERN = ZoneInfo("America/New_York")
Clock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]


def _eastern_now() -> datetime:
    return datetime.now(_EASTERN)


class App:
    """Fetch, select, and deliver alerts while keeping a successful-run anchor."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient,
        *,
        clock: Clock = _eastern_now,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.settings = settings
        self.client = client
        self.clock = clock
        self.sleep = sleep
        self.interval_seconds = settings.minutes_between_runs * 60
        self.last_success: datetime | None = None

    async def poll(self, now: datetime) -> int:
        """Poll at an aware time and return the number of selected alerts."""
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("poll time must be timezone-aware")

        now = now.astimezone(_EASTERN)
        previous_run = self.last_success
        if previous_run is None:
            previous_run = (now.astimezone(UTC) - timedelta(seconds=self.interval_seconds)).astimezone(_EASTERN)

        rows = await stockcharts.fetch_alerts(self.client, sleep=self.sleep)
        valid_alerts = alerts.filter_alerts(rows)
        selected_alerts = alerts.new_alerts_since(valid_alerts, previous_run)
        for alert in selected_alerts:
            await discord.send_alert_to_webhooks(
                self.client,
                alert,
                self.settings.webhook_urls,
            )

        self.last_success = now
        return len(selected_alerts)

    async def run(self) -> None:
        """Poll immediately, then repeat at the configured interval or backoff."""
        try:
            count = await self.poll(self.clock())
        except Exception:
            logger.error("initial alert check failed")
        else:
            logger.info("initial alert check completed; alerts_sent=%d", count)

        consecutive_errors = 0
        next_delay = self.interval_seconds
        while True:
            await self.sleep(next_delay)
            try:
                count = await self.poll(self.clock())
            except Exception:
                consecutive_errors += 1
                logger.error(
                    "alert check failed; consecutive_errors=%d",
                    consecutive_errors,
                )
                next_delay = 300 if consecutive_errors >= 5 else 60
            else:
                consecutive_errors = 0
                next_delay = self.interval_seconds
                logger.info("alert check completed; alerts_sent=%d", count)
