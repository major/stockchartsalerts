"""Polling and delivery orchestration for StockCharts alerts."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from stockchartsalerts import alerts, discord, stockcharts

if TYPE_CHECKING:
    import httpx2

    from stockchartsalerts.config import Settings

logger = logging.getLogger(__name__)
_EASTERN = ZoneInfo("America/New_York")
_LONG_BACKOFF_FAILURE_THRESHOLD = 5
Clock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]


class _NaivePollTimeError(ValueError):
    def __init__(self) -> None:
        super().__init__("poll time must be timezone-aware")


def _eastern_now() -> datetime:
    return datetime.now(_EASTERN)


class App:
    """Fetch, select, and deliver alerts while keeping a successful-run anchor."""

    def __init__(
        self,
        settings: Settings,
        client: httpx2.AsyncClient,
        *,
        clock: Clock = _eastern_now,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        """Initialize polling with the shared client and injectable timing functions."""
        self.settings = settings
        self.client = client
        self.clock = clock
        self.sleep = sleep
        self.interval_seconds = settings.minutes_between_runs * 60
        self.last_success: datetime | None = None

    async def poll(self, now: datetime) -> int:
        """Poll at an aware time and return the number of selected alerts."""
        if now.tzinfo is None or now.utcoffset() is None:
            raise _NaivePollTimeError()

        now = now.astimezone(_EASTERN)
        previous_run = self.last_success
        if previous_run is None:
            previous_run = (now.astimezone(UTC) - timedelta(seconds=self.interval_seconds)).astimezone(_EASTERN)

        rows = await stockcharts.fetch_alerts(self.client, sleep=self.sleep)
        selection = alerts.select_alerts(rows, previous_run)
        if selection.malformed_rows or selection.invalid_timestamps:
            logger.warning(
                "StockCharts rows rejected; malformed_rows=%d invalid_timestamps=%d",
                selection.malformed_rows,
                selection.invalid_timestamps,
            )
        for alert in selection.selected:
            await discord.send_alert_to_webhooks(
                self.client,
                alert,
                self.settings.webhook_urls,
            )

        self.last_success = now
        return len(selection.selected)

    async def run(self) -> None:
        """Poll immediately, then repeat at the configured interval or backoff."""
        try:
            count = await self.poll(self.clock())
        except stockcharts.FetchError as error:
            # Keep the sanitized fetch message without a traceback.
            logger.error("initial alert check failed: %s", str(error))  # noqa: TRY400
        # Recover from ordinary poll failures without exposing exception details.
        except Exception as error:  # noqa: BLE001
            logger.error("initial alert check failed; error_type=%s", type(error).__name__)  # noqa: TRY400
        else:
            logger.info("initial alert check completed; alerts_sent=%d", count)

        consecutive_errors = 0
        next_delay = self.interval_seconds
        while True:
            await self.sleep(next_delay)
            try:
                count = await self.poll(self.clock())
            except stockcharts.FetchError as error:
                consecutive_errors += 1
                # Keep the sanitized fetch message without a traceback.
                logger.error(  # noqa: TRY400
                    "alert check failed; consecutive_errors=%d; error=%s",
                    consecutive_errors,
                    str(error),
                )
                next_delay = 300 if consecutive_errors >= _LONG_BACKOFF_FAILURE_THRESHOLD else 60
            # Recover from ordinary poll failures without exposing exception details.
            except Exception as error:  # noqa: BLE001
                consecutive_errors += 1
                logger.error(  # noqa: TRY400
                    "alert check failed; consecutive_errors=%d; error_type=%s",
                    consecutive_errors,
                    type(error).__name__,
                )
                next_delay = 300 if consecutive_errors >= _LONG_BACKOFF_FAILURE_THRESHOLD else 60
            else:
                consecutive_errors = 0
                next_delay = self.interval_seconds
                logger.info("alert check completed; alerts_sent=%d", count)
