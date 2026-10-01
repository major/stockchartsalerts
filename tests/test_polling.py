"""Behavior tests for poll results, lookback windows, and scheduler recovery."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx2
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
        discord_requests: list[httpx2.Request] = []

        def handle(request: httpx2.Request) -> httpx2.Response:
            nonlocal stockcharts_requests
            if request.url.host == "stockcharts.com":
                stockcharts_requests += 1
                if stockcharts_requests == 1:
                    return httpx2.Response(
                        200,
                        json=[
                            {
                                "alert": "First alert",
                                "bearish": "no",
                                "lastfired": "1 Jan 2024, 10:02am",
                                "symbol": "FIRST",
                            },
                        ],
                    )
                if stockcharts_requests < 5:
                    return httpx2.Response(503)
                if stockcharts_requests == 5:
                    return httpx2.Response(
                        200,
                        json=[
                            {
                                "alert": "Alert during outage",
                                "bearish": "yes",
                                "lastfired": "1 Jan 2024, 10:10am",
                                "symbol": "LATER",
                            },
                        ],
                    )
                return httpx2.Response(
                    200,
                    json=[
                        {
                            "alert": "Older than recovery poll",
                            "bearish": "no",
                            "lastfired": "1 Jan 2024, 10:20am",
                            "symbol": "STALE",
                        },
                    ],
                )

            discord_requests.append(request)
            return httpx2.Response(500)

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
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
        def unexpected_request(_request: httpx2.Request) -> httpx2.Response:
            raise AssertionError("poll should reject the time before making a request")

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(unexpected_request)) as client:
            application = App(_settings(), client, sleep=_no_wait)
            with pytest.raises(ValueError, match="timezone-aware"):
                await application.poll(datetime(2024, 1, 1, 10, 5))

    asyncio.run(scenario())


def test_poll_logs_aggregate_rejections_and_delivers_healthy_rows(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        discord_requests: list[httpx2.Request] = []
        rows = [
            {
                "alert": "Healthy neighbor",
                "bearish": "no",
                "lastfired": "1 Jan 2024, 10:02am",
                "symbol": "GOOD",
            },
            {
                "alert": "Superseded alert",
                "bearish": "no",
                "lastfired": "1 Jan 2024, 10:01am",
                "symbol": "TIED",
            },
            {
                "alert": "Latest alert",
                "bearish": "no",
                "lastfired": "1 Jan 2024, 10:03am",
                "symbol": "TIED",
            },
            {
                "alert": "Latest tie",
                "bearish": "yes",
                "lastfired": "1 Jan 2024, 10:03am",
                "symbol": "TIED",
            },
            None,
            {
                "alert": 7,
                "ALERT": "malformed-secret-alert",
                "lastfired": "1 Jan 2024, 10:02am",
                "symbol": "malformed-secret-symbol",
            },
            {
                "alert": "Overflow alert",
                "lastfired": "31 Dec 9999, 11:59pm",
                "symbol": "OVERFLOW_SECRET",
            },
            {
                "alert": "Invalid timestamp alert",
                "lastfired": "not a timestamp secret",
                "symbol": "INVALID_SECRET",
            },
            {"alert": "Missing timestamp alert", "symbol": "MISSING"},
            {
                "alert": " There are no alerts today ",
                "lastfired": "not a timestamp",
                "symbol": "PLACEHOLDER",
            },
        ]

        def handle(request: httpx2.Request) -> httpx2.Response:
            if request.url.host == "stockcharts.com":
                return httpx2.Response(200, json=rows)

            discord_requests.append(request)
            return httpx2.Response(204)

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
            application = App(_settings(), client, sleep=_no_wait)
            assert await application.poll(datetime(2024, 1, 1, 10, 5, tzinfo=_EASTERN)) == 3

        assert [json.loads(request.content)["content"] for request in discord_requests] == [
            "💚  Healthy neighbor",
            "💚  Latest alert",
            "🔴  Latest tie",
        ]

    with caplog.at_level(logging.WARNING, logger="stockchartsalerts.app"):
        asyncio.run(scenario())

    rejection_logs = [
        record
        for record in caplog.records
        if record.name == "stockchartsalerts.app" and record.levelno == logging.WARNING
    ]
    assert len(rejection_logs) == 1
    rejection_message = rejection_logs[0].getMessage()
    assert "malformed_rows=2" in rejection_message
    assert "invalid_timestamps=3" in rejection_message
    assert "malformed-secret" not in caplog.text
    assert "OVERFLOW_SECRET" not in caplog.text
    assert "INVALID_SECRET" not in caplog.text
    assert "not a timestamp secret" not in caplog.text


def test_poll_delivers_healthy_alert_after_placeholder_without_rejection_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        discord_requests: list[httpx2.Request] = []
        rows = [
            {"alert": "There are no alerts today"},
            {
                "alert": "Healthy alert after placeholder",
                "bearish": "no",
                "lastfired": "1 Jan 2024, 10:02am",
                "symbol": "GOOD",
            },
        ]

        def handle(request: httpx2.Request) -> httpx2.Response:
            if request.url.host == "stockcharts.com":
                return httpx2.Response(200, json=rows)

            discord_requests.append(request)
            return httpx2.Response(204)

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
            application = App(_settings(), client, sleep=_no_wait)
            # The initial lookback anchor is exactly 10:00 a.m. Eastern.
            assert await application.poll(datetime(2024, 1, 1, 10, 5, tzinfo=_EASTERN)) == 1

        assert [json.loads(request.content)["content"] for request in discord_requests] == [
            "💚  Healthy alert after placeholder",
        ]

    with caplog.at_level(logging.WARNING, logger="stockchartsalerts.app"):
        asyncio.run(scenario())

    assert not [
        record
        for record in caplog.records
        if record.name == "stockchartsalerts.app" and record.levelno == logging.WARNING
    ]


def test_poll_counts_non_object_rows_and_delivers_healthy_neighbor(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        discord_requests: list[httpx2.Request] = []
        rows: list[object] = [
            None,
            {
                "alert": "Healthy neighbor",
                "bearish": "no",
                "lastfired": "1 Jan 2024, 10:02am",
                "symbol": "GOOD",
            },
            ["private-array-row-data"],
        ]

        def handle(request: httpx2.Request) -> httpx2.Response:
            if request.url.host == "stockcharts.com":
                return httpx2.Response(200, json=rows)

            discord_requests.append(request)
            return httpx2.Response(204)

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
            application = App(_settings(), client, sleep=_no_wait)
            now = datetime(2024, 1, 1, 10, 5, tzinfo=_EASTERN)
            assert await application.poll(now) == 1

        assert len(discord_requests) == 1
        payload = json.loads(discord_requests[0].content)
        assert payload["username"] == "GOOD"
        assert payload["content"] == "💚  Healthy neighbor"

    with caplog.at_level(logging.WARNING, logger="stockchartsalerts.app"):
        asyncio.run(scenario())

    rejection_logs = [
        record
        for record in caplog.records
        if record.name == "stockchartsalerts.app" and record.levelno == logging.WARNING
    ]
    assert len(rejection_logs) == 1
    rejection_message = rejection_logs[0].getMessage()
    assert "malformed_rows=2" in rejection_message
    assert "invalid_timestamps=0" in rejection_message
    assert "private-array-row-data" not in caplog.text


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
                },
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
        discord_requests: list[httpx2.Request] = []

        def handle(request: httpx2.Request) -> httpx2.Response:
            if request.url.host == "stockcharts.com":
                return httpx2.Response(200, json=rows)

            discord_requests.append(request)
            return httpx2.Response(204)

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
            application = App(_settings(), client, sleep=_no_wait)
            assert await application.poll(now) == 1

        assert len(discord_requests) == 1
        assert expected_alert in discord_requests[0].content

    asyncio.run(scenario())


def test_startup_failure_keeps_interval_and_recurring_errors_back_off(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        delays: list[float] = []
        events: list[str] = []

        def always_fail(request: httpx2.Request) -> httpx2.Response:
            assert request.url.host == "stockcharts.com"
            events.append("fetch")
            return httpx2.Response(503, text="upstream-private-response")

        async def controlled_sleep(seconds: float) -> None:
            if seconds > 4:
                delays.append(seconds)
                events.append(f"scheduled-wait:{seconds:g}")
                if len(delays) == 6:
                    raise asyncio.CancelledError

        now = datetime(2024, 1, 1, 10, 5, tzinfo=_EASTERN)
        with caplog.at_level(logging.ERROR, logger="stockchartsalerts.app"):
            async with httpx2.AsyncClient(transport=httpx2.MockTransport(always_fail)) as client:
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
    app_error_logs = [
        record
        for record in caplog.records
        if record.name == "stockchartsalerts.app" and record.levelno == logging.ERROR
    ]
    assert [record.getMessage() for record in app_error_logs] == [
        "initial alert check failed: StockCharts returned HTTP status 503",
        *[
            f"alert check failed; consecutive_errors={count}; error=StockCharts returned HTTP status 503"
            for count in range(1, 6)
        ],
    ]
    assert "upstream-private-response" not in caplog.text
    assert all(record.exc_info is None for record in app_error_logs)


def test_scheduler_logs_unexpected_exception_types_and_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        clock_calls = 0
        delays: list[float] = []
        now = datetime(2024, 1, 1, 10, 5, tzinfo=_EASTERN)

        def changing_clock() -> datetime:
            nonlocal clock_calls
            clock_calls += 1
            if clock_calls == 1:
                raise RuntimeError("startup-private-detail")
            if clock_calls == 2:
                return now
            raise ValueError("recurring-private-detail")

        def empty_feed(request: httpx2.Request) -> httpx2.Response:
            assert request.url.host == "stockcharts.com"
            return httpx2.Response(200, json=[])

        async def controlled_sleep(seconds: float) -> None:
            delays.append(seconds)
            if len(delays) == 3:
                raise asyncio.CancelledError

        with caplog.at_level(logging.ERROR, logger="stockchartsalerts.app"):
            async with httpx2.AsyncClient(transport=httpx2.MockTransport(empty_feed)) as client:
                application = App(
                    _settings(),
                    client,
                    clock=changing_clock,
                    sleep=controlled_sleep,
                )
                with pytest.raises(asyncio.CancelledError):
                    await application.run()

        assert delays == [300, 300, 60]

    asyncio.run(scenario())
    app_error_logs = [
        record
        for record in caplog.records
        if record.name == "stockchartsalerts.app" and record.levelno == logging.ERROR
    ]
    assert [record.getMessage() for record in app_error_logs] == [
        "initial alert check failed; error_type=RuntimeError",
        "alert check failed; consecutive_errors=1; error_type=ValueError",
    ]
    assert "startup-private-detail" not in caplog.text
    assert "recurring-private-detail" not in caplog.text
    assert all(record.exc_info is None for record in app_error_logs)


def test_success_restores_the_regular_interval_after_a_recurring_failure() -> None:
    async def scenario() -> None:
        delays: list[float] = []
        requests = 0

        def fail_startup_and_first_recurring_poll(request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            assert request.url.host == "stockcharts.com"
            requests += 1
            if requests <= 6:
                return httpx2.Response(503)
            return httpx2.Response(200, json=[])

        async def controlled_sleep(seconds: float) -> None:
            if seconds > 4:
                delays.append(seconds)
                if len(delays) == 3:
                    raise asyncio.CancelledError

        now = datetime(2024, 1, 1, 10, 5, tzinfo=_EASTERN)
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(fail_startup_and_first_recurring_poll)) as client:
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

        def empty_feed(request: httpx2.Request) -> httpx2.Response:
            assert request.url.host == "stockcharts.com"
            return httpx2.Response(200, json=[])

        async def controlled_sleep(_seconds: float) -> None:
            waiting.set()
            await asyncio.Future()

        now = datetime(2024, 1, 1, 10, 5, tzinfo=_EASTERN)
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(empty_feed)) as client:
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

        async def hold_request(request: httpx2.Request) -> httpx2.Response:
            assert request.url.host == "stockcharts.com"
            request_started.set()
            await asyncio.Future()

        now = datetime(2024, 1, 1, 10, 5, tzinfo=_EASTERN)
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(hold_request)) as client:
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
