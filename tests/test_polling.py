"""Behavior tests for poll results, lookback windows, and scheduler recovery."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from stockchartsalerts.app import App
from stockchartsalerts.config import Settings
from stockchartsalerts.stockcharts import FetchError

_EASTERN = ZoneInfo("America/New_York")


def _settings(*, webhook_urls: tuple[str, ...] = ("https://discord.test/webhook",)) -> Settings:
    return Settings(
        webhook_urls=webhook_urls,
        minutes_between_runs=5,
        git_commit="abc123",
        git_branch="main",
        log_level="info",
    )


async def _no_wait(_seconds: float) -> None:
    return None


def test_poll_recovers_after_fetch_outage_and_advances_the_delivery_window() -> None:
    async def scenario() -> None:
        webhook_urls = (
            "https://discord.test/webhook/one",
            "https://discord.test/webhook/two",
        )
        settings = _settings(webhook_urls=webhook_urls)
        stockcharts_requests = 0
        discord_requests: list[httpx.Request] = []

        def handle(request: httpx.Request) -> httpx.Response:
            nonlocal stockcharts_requests
            if request.url.host == "stockcharts.com":
                stockcharts_requests += 1
                if stockcharts_requests == 1:
                    return httpx.Response(
                        200,
                        json=[
                            {
                                "alert": "First alert",
                                "bearish": "no",
                                "lastfired": "1 Jan 2024, 10:02am",
                                "symbol": "FIRST",
                            }
                        ],
                    )
                if stockcharts_requests < 5:
                    return httpx.Response(503)
                if stockcharts_requests == 5:
                    return httpx.Response(
                        200,
                        json=[
                            {
                                "alert": "Alert during outage",
                                "bearish": "yes",
                                "lastfired": "1 Jan 2024, 10:10am",
                                "symbol": "LATER",
                            }
                        ],
                    )
                return httpx.Response(
                    200,
                    json=[
                        {
                            "alert": "Older than recovery poll",
                            "bearish": "no",
                            "lastfired": "1 Jan 2024, 10:20am",
                            "symbol": "STALE",
                        }
                    ],
                )

            discord_requests.append(request)
            return httpx.Response(500)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            application = App(settings, client, sleep=_no_wait)
            first_poll = datetime(2024, 1, 1, 15, 5, tzinfo=UTC)
            outage_poll = datetime(2024, 1, 1, 15, 30, tzinfo=UTC)
            following_poll = datetime(2024, 1, 1, 15, 35, tzinfo=UTC)

            assert await application.poll(first_poll) == 1
            with pytest.raises(FetchError):
                await application.poll(outage_poll)

            # This alert is older than the outage poll's normal interval, but
            # remains newer than the last successful poll and must be delivered.
            assert await application.poll(outage_poll) == 1

            # A later response older than the recovery poll must not be repeated.
            assert await application.poll(following_poll) == 0

        assert [str(request.url) for request in discord_requests] == [
            str(webhook_urls[0]),
            str(webhook_urls[1]),
            str(webhook_urls[0]),
            str(webhook_urls[1]),
        ]
        assert all(request.method == "POST" for request in discord_requests)
        assert [b"First alert" in request.content for request in discord_requests] == [
            True,
            True,
            False,
            False,
        ]
        assert [b"Alert during outage" in request.content for request in discord_requests] == [
            False,
            False,
            True,
            True,
        ]

    asyncio.run(scenario())


def test_poll_rejects_naive_time_without_fetching() -> None:
    async def scenario() -> None:
        def unexpected_request(_request: httpx.Request) -> httpx.Response:
            raise AssertionError("poll should reject the time before making a request")

        async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected_request)) as client:
            application = App(_settings(), client, sleep=_no_wait)
            with pytest.raises(ValueError, match="timezone-aware"):
                await application.poll(datetime(2024, 1, 1, 10, 5))

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("now", "rows", "expected_alert"),
    [
        (
            datetime(2024, 3, 10, 3, 2, tzinfo=_EASTERN),
            [
                {
                    "alert": "recent spring alert",
                    "bearish": "no",
                    "lastfired": "10 Mar 2024, 3:01am",
                    "symbol": "RECENT",
                }
            ],
            b"recent spring alert",
        ),
        (
            datetime(2024, 11, 3, 1, 2, tzinfo=_EASTERN, fold=1),
            [
                {
                    "alert": "older early-fold alert",
                    "bearish": "no",
                    "lastfired": "3 Nov 2024, 12:59am",
                    "symbol": "OLD",
                },
                {
                    "alert": "recent fall alert",
                    "bearish": "no",
                    "lastfired": "3 Nov 2024, 1:59am",
                    "symbol": "RECENT",
                },
            ],
            b"recent fall alert",
        ),
    ],
    ids=("spring-forward-elapsed-time", "fall-back-fold-elapsed-time"),
)
def test_initial_lookback_uses_elapsed_time_across_dst(
    now: datetime,
    rows: list[object],
    expected_alert: bytes,
) -> None:
    async def scenario() -> None:
        discord_requests: list[httpx.Request] = []

        def handle(request: httpx.Request) -> httpx.Response:
            if request.url.host == "stockcharts.com":
                return httpx.Response(200, json=rows)

            discord_requests.append(request)
            return httpx.Response(204)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            application = App(_settings(), client, sleep=_no_wait)
            assert await application.poll(now) == 1

        assert len(discord_requests) == 1
        assert expected_alert in discord_requests[0].content

    asyncio.run(scenario())


def test_startup_failure_keeps_interval_and_recurring_errors_back_off() -> None:
    async def scenario() -> None:
        delays: list[float] = []
        events: list[str] = []

        def always_fail(request: httpx.Request) -> httpx.Response:
            assert request.url.host == "stockcharts.com"
            events.append("fetch")
            return httpx.Response(503)

        async def controlled_sleep(seconds: float) -> None:
            if seconds > 4:
                delays.append(seconds)
                events.append(f"scheduled-wait:{seconds:g}")
                if len(delays) == 6:
                    raise asyncio.CancelledError

        now = datetime(2024, 1, 1, 10, 5, tzinfo=_EASTERN)
        async with httpx.AsyncClient(transport=httpx.MockTransport(always_fail)) as client:
            application = App(
                _settings(),
                client,
                clock=lambda: now,
                sleep=controlled_sleep,
            )
            with pytest.raises(asyncio.CancelledError):
                await application.run()

        # The startup failure does not count toward recurring backoff. Five
        # recurring failures change the next wait from 60 to 300 seconds.
        assert events[0] == "fetch"
        assert delays == [300, 60, 60, 60, 60, 300]

    asyncio.run(scenario())


def test_success_restores_the_regular_interval_after_a_recurring_failure() -> None:
    async def scenario() -> None:
        delays: list[float] = []
        requests = 0

        def fail_startup_and_first_recurring_poll(request: httpx.Request) -> httpx.Response:
            nonlocal requests
            assert request.url.host == "stockcharts.com"
            requests += 1
            if requests <= 6:
                return httpx.Response(503)
            return httpx.Response(200, json=[])

        async def controlled_sleep(seconds: float) -> None:
            if seconds > 4:
                delays.append(seconds)
                if len(delays) == 3:
                    raise asyncio.CancelledError

        now = datetime(2024, 1, 1, 10, 5, tzinfo=_EASTERN)
        async with httpx.AsyncClient(transport=httpx.MockTransport(fail_startup_and_first_recurring_poll)) as client:
            application = App(
                _settings(),
                client,
                clock=lambda: now,
                sleep=controlled_sleep,
            )
            with pytest.raises(asyncio.CancelledError):
                await application.run()

        assert delays == [300, 60, 300]

    asyncio.run(scenario())


def test_cancellation_interrupts_scheduler_wait() -> None:
    async def scenario() -> None:
        waiting = asyncio.Event()

        def empty_feed(request: httpx.Request) -> httpx.Response:
            assert request.url.host == "stockcharts.com"
            return httpx.Response(200, json=[])

        async def controlled_sleep(_seconds: float) -> None:
            waiting.set()
            await asyncio.Future()

        now = datetime(2024, 1, 1, 10, 5, tzinfo=_EASTERN)
        async with httpx.AsyncClient(transport=httpx.MockTransport(empty_feed)) as client:
            application = App(
                _settings(),
                client,
                clock=lambda: now,
                sleep=controlled_sleep,
            )
            task = asyncio.create_task(application.run())
            await waiting.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(scenario())


def test_cancellation_interrupts_in_flight_fetch() -> None:
    async def scenario() -> None:
        request_started = asyncio.Event()

        async def hold_request(request: httpx.Request) -> httpx.Response:
            assert request.url.host == "stockcharts.com"
            request_started.set()
            await asyncio.Future()

        now = datetime(2024, 1, 1, 10, 5, tzinfo=_EASTERN)
        async with httpx.AsyncClient(transport=httpx.MockTransport(hold_request)) as client:
            application = App(
                _settings(),
                client,
                clock=lambda: now,
                sleep=_no_wait,
            )
            task = asyncio.create_task(application.run())
            await request_started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(scenario())
