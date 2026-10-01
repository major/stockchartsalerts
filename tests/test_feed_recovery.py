"""StockCharts feed request, decoding, retry, and cancellation behavior."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

import httpx2
import pytest

from stockchartsalerts.stockcharts import DEFAULT_ENDPOINT, FetchError, fetch_alerts

_REFERER = "https://stockcharts.com/freecharts/alertsummary.html"
_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0"


def test_fetch_alerts_sends_required_request_and_returns_json_array() -> None:
    async def scenario() -> None:
        async def handle(request: httpx2.Request) -> httpx2.Response:
            assert request.method == "GET"
            assert str(request.url) == DEFAULT_ENDPOINT
            assert request.headers["Referer"] == _REFERER
            assert request.headers["User-Agent"] == _USER_AGENT
            return httpx2.Response(200, json=[{"symbol": "SPX"}, "raw row"])

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
            assert await fetch_alerts(client) == [{"symbol": "SPX"}, "raw row"]

    asyncio.run(scenario())


def test_fetch_alerts_retries_status_failures_with_two_and_four_second_delays(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        requests = 0
        delays: list[float] = []

        def handle(_request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            if requests < 3:
                return httpx2.Response(503)
            return httpx2.Response(201, json=[])

        async def record_sleep(seconds: float) -> None:
            delays.append(seconds)

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
            assert await fetch_alerts(client, sleep=record_sleep, endpoint="https://feed.test") == []

        assert requests == 3
        assert delays == [2.0, 4.0]

    with caplog.at_level(logging.WARNING):
        asyncio.run(scenario())
    assert "StockCharts returned HTTP status 503" in caplog.text
    assert "retrying attempt=1" in caplog.text
    assert "retrying attempt=2" in caplog.text


@pytest.mark.parametrize(
    ("body", "failure_reason"),
    [
        (b"not json", "StockCharts response was not valid JSON"),
        (b'{"alerts": []}', "StockCharts response was not a JSON array"),
    ],
)
def test_fetch_alerts_retries_malformed_or_non_array_json(
    body: bytes,
    failure_reason: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        requests = 0
        delays: list[float] = []

        def handle(_request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            return httpx2.Response(200, content=body)

        async def record_sleep(seconds: float) -> None:
            delays.append(seconds)

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
            with pytest.raises(FetchError) as captured:
                await fetch_alerts(
                    client,
                    sleep=record_sleep,
                    endpoint="https://feed.test/secret?token=private",
                )

        assert requests == 3
        assert delays == [2.0, 4.0]
        assert failure_reason in str(captured.value)
        assert "secret" not in str(captured.value)
        assert "private" not in str(captured.value)

    with caplog.at_level(logging.WARNING):
        asyncio.run(scenario())
    assert failure_reason in caplog.text
    assert "retrying attempt=1" in caplog.text
    assert "retrying attempt=2" in caplog.text
    assert "private" not in caplog.text
    assert "feed.test" not in caplog.text


def test_fetch_alerts_sanitizes_transport_errors_and_retries(caplog: pytest.LogCaptureFixture) -> None:
    async def scenario() -> None:
        requests = 0
        delays: list[float] = []

        def fail_with_secret(request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            raise httpx2.ConnectError("secret transport details", request=request)

        async def record_sleep(seconds: float) -> None:
            delays.append(seconds)

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(fail_with_secret)) as client:
            with pytest.raises(FetchError) as captured:
                await fetch_alerts(
                    client,
                    sleep=record_sleep,
                    endpoint="https://feed.test/secret?token=private",
                )

        assert requests == 3
        assert delays == [2.0, 4.0]
        assert str(captured.value) == "StockCharts request failed"
        assert "secret" not in str(captured.value)

    with caplog.at_level(logging.WARNING):
        asyncio.run(scenario())
    assert "private" not in caplog.text
    assert "feed.test" not in caplog.text
    assert "StockCharts request failed" in caplog.text
    assert "retrying attempt=1" in caplog.text
    assert "retrying attempt=2" in caplog.text


def test_fetch_alerts_deadline_covers_response_body_read_and_retries(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        requests = 0
        body_reads = 0
        delays: list[float] = []

        class HangingBody(httpx2.AsyncByteStream):
            async def __aiter__(self) -> AsyncIterator[bytes]:
                nonlocal body_reads
                yield b"["
                body_reads += 1
                await asyncio.Future()

            async def aclose(self) -> None:
                return None

        def handle(_request: httpx2.Request) -> httpx2.Response:
            nonlocal requests
            requests += 1
            return httpx2.Response(200, stream=HangingBody())

        async def record_sleep(seconds: float) -> None:
            delays.append(seconds)

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
            with pytest.raises(FetchError) as captured:
                await fetch_alerts(
                    client,
                    sleep=record_sleep,
                    endpoint="https://feed.test/secret?token=private",
                    request_timeout=0.0,
                )

        assert requests == 3
        assert body_reads == 3
        assert delays == [2.0, 4.0]
        assert str(captured.value) == "StockCharts request failed"
        assert "private" not in str(captured.value)

    with caplog.at_level(logging.WARNING):
        asyncio.run(scenario())
    assert "private" not in caplog.text
    assert "feed.test" not in caplog.text
    assert "StockCharts request failed" in caplog.text
    assert "retrying attempt=1" in caplog.text
    assert "retrying attempt=2" in caplog.text


def test_fetch_alerts_propagates_cancellation_during_request() -> None:
    async def scenario() -> None:
        started = asyncio.Event()

        async def hold_request(_request: httpx2.Request) -> httpx2.Response:
            started.set()
            await asyncio.Future()
            raise AssertionError("unreachable")

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(hold_request)) as client:
            task = asyncio.create_task(fetch_alerts(client, endpoint="https://feed.test"))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(scenario())
