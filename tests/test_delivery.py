"""Discord delivery and secret-safe logging behavior."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx2
import pytest

from stockchartsalerts.alerts import Alert
from stockchartsalerts.app import App
from stockchartsalerts.config import Settings
from stockchartsalerts.discord import send_alert_to_webhooks
from stockchartsalerts.telemetry import configure_logging

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.mark.parametrize(
    ("bearish", "text", "expected_content"),
    [
        ("yes", "Dow crosses above 41000", "🔴  THE DOW, THE DOW IS ABOVE 41000"),
        ("no", "Other alert", "💚  Other alert"),
        ("YES", "Dow crosses above ", "💚  THE DOW, THE DOW IS ABOVE "),
        ("no", "dow crosses above 41000", "💚  dow crosses above 41000"),
    ],
)
def test_delivery_sends_formatted_discord_payload(
    bearish: str,
    text: str,
    expected_content: str,
) -> None:
    """Send the expected icon and text in the Discord payload."""

    async def scenario() -> None:
        payloads: list[dict[str, object]] = []

        def handle(request: httpx2.Request) -> httpx2.Response:
            assert request.method == "POST"
            payloads.append(json.loads(request.content))
            return httpx2.Response(204)

        alert = Alert(bearish=bearish, symbol="$INDU", alert=text, lastfired="31 Jul 2024, 12:33pm")
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
            await send_alert_to_webhooks(client, alert, ("https://discord.test/webhooks/test",))

        assert payloads == [
            {
                "username": "$INDU",
                "avatar_url": "https://emojiguide.org/images/emoji/1/8z8e40kucdd1.png",
                "content": expected_content,
            },
        ]

    asyncio.run(scenario())


def test_webhooks_are_posted_sequentially_and_failures_do_not_stop_later_urls() -> None:
    """Attempt configured webhooks sequentially after a failure."""

    async def scenario() -> None:
        requests: list[str] = []
        payloads: list[dict[str, object]] = []
        active_requests = 0
        maximum_active_requests = 0

        async def handle(request: httpx2.Request) -> httpx2.Response:
            nonlocal active_requests, maximum_active_requests
            requests.append(request.url.path)
            payloads.append(json.loads(request.content))
            active_requests += 1
            maximum_active_requests = max(maximum_active_requests, active_requests)
            await asyncio.sleep(0)
            active_requests -= 1
            if request.url.path.endswith("first"):
                return httpx2.Response(500)
            if request.url.path.endswith("second"):
                return httpx2.Response(202)
            return httpx2.Response(204)

        alert = Alert(
            bearish="no",
            symbol="$COMPQ",
            alert="Test alert",
            lastfired="31 Jul 2024, 12:33pm",
        )
        urls = [
            "https://discord.test/webhooks/first?token=first-secret",
            "https://discord.test/webhooks/second?token=second-secret",
            "https://discord.test/webhooks/third?token=third-secret",
        ]
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
            await send_alert_to_webhooks(client, alert, urls)

        assert requests == ["/webhooks/first", "/webhooks/second", "/webhooks/third"]
        assert maximum_active_requests == 1
        assert (
            payloads
            == [
                {
                    "username": "$COMPQ",
                    "avatar_url": "https://emojiguide.org/images/emoji/1/8z8e40kucdd1.png",
                    "content": "💚  Test alert",
                },
            ]
            * 3
        )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("configured", "debug_is_visible"),
    [("info", False), ("debug", True)],
)
def test_delivery_logs_keep_webhook_secrets_private_at_configured_levels(
    configured: str,
    debug_is_visible: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Keep webhook secrets private at each supported logging level."""

    async def scenario() -> None:
        request_urls: list[str] = []
        payloads: list[dict[str, object]] = []

        def handle(request: httpx2.Request) -> httpx2.Response:
            request_urls.append(str(request.url))
            if request.url.host == "stockcharts.com":
                return httpx2.Response(
                    200,
                    json=[
                        {
                            "alert": "Test alert",
                            "bearish": "no",
                            "lastfired": "1 Jan 2024, 10:04am",
                            "symbol": "TEST",
                        },
                    ],
                )
            payloads.append(json.loads(request.content))
            return httpx2.Response(204)

        settings = Settings(
            webhook_urls=("https://discord.test/api/webhooks/token-secret?wait=true",),
            minutes_between_runs=5,
            git_commit="abc123",
            git_branch="main",
            log_level=configured,
        )
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
            application = App(settings, client, sleep=lambda _seconds: asyncio.sleep(0))
            assert await application.poll(datetime(2024, 1, 1, 15, 5, tzinfo=UTC)) == 1

        assert request_urls == [
            "https://stockcharts.com/j-sum/sum?cmd=alert",
            "https://discord.test/api/webhooks/token-secret?wait=true",
        ]
        assert payloads == [
            {
                "username": "TEST",
                "avatar_url": "https://emojiguide.org/images/emoji/1/8z8e40kucdd1.png",
                "content": "💚  Test alert",
            },
        ]

    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="httpx2")
    caplog.set_level(logging.DEBUG, logger="httpcore2")
    assert configure_logging(configured) == configured
    logging.getLogger("stockchartsalerts.app").debug("application debug marker")
    asyncio.run(scenario())

    assert "alert sent to Discord" in caplog.text
    assert "token-secret" not in caplog.text
    assert "wait=true" not in caplog.text
    assert "discord.test" not in caplog.text
    assert (
        "application debug marker" in caplog.text if debug_is_visible else "application debug marker" not in caplog.text
    )


@pytest.mark.parametrize(
    ("configured", "normalized", "visible_levels"),
    [
        (" DEBUG ", "debug", ("debug", "info", "warning", "error")),
        ("info", "info", ("info", "warning", "error")),
        ("WaRn", "warn", ("warning", "error")),
        ("ERROR", "error", ("error",)),
        ("trace", "info", ("info", "warning", "error")),
        ("", "info", ("info", "warning", "error")),
    ],
)
def test_configure_logging_emits_messages_at_normalized_level(
    configured: str,
    normalized: str,
    visible_levels: tuple[str, ...],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Emit messages only at the normalized logging level."""
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="httpx2")
    caplog.set_level(logging.DEBUG, logger="httpcore2")
    assert configure_logging(configured) == normalized

    app_logger = logging.getLogger("stockchartsalerts.app")
    app_logger.debug("logging-level marker: debug")
    app_logger.info("logging-level marker: info")
    app_logger.warning("logging-level marker: warning")
    app_logger.error("logging-level marker: error")

    for level in ("debug", "info", "warning", "error"):
        assert (f"logging-level marker: {level}" in caplog.text) == (level in visible_levels)


def test_webhook_transport_failure_is_sanitized_and_delivery_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sanitize transport failures and continue to remaining webhooks."""

    async def scenario() -> None:
        requests: list[str] = []

        def fail_first(request: httpx2.Request) -> httpx2.Response:
            requests.append(request.url.path)
            if request.url.path.endswith("first"):
                raise httpx2.ConnectError("first-secret leaked by transport", request=request)
            return httpx2.Response(200)

        alert = Alert(
            bearish="yes",
            symbol="$SPX",
            alert="Test alert",
            lastfired="31 Jul 2024, 12:33pm",
        )
        urls = [
            "https://discord.test/webhooks/first?token=first-secret",
            "https://discord.test/webhooks/second?token=second-secret",
        ]
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(fail_first)) as client:
            await send_alert_to_webhooks(client, alert, urls)

        assert requests == ["/webhooks/first", "/webhooks/second"]

    with caplog.at_level(logging.ERROR):
        asyncio.run(scenario())
    assert "Discord webhook failed" in caplog.text
    assert "error=ConnectError" in caplog.text
    assert "first-secret" not in caplog.text
    assert "second-secret" not in caplog.text
    assert "discord.test" not in caplog.text


def test_invalid_webhook_url_is_sanitized_and_delivery_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sanitize invalid webhook URLs and continue delivery."""

    async def scenario() -> None:
        requests: list[str] = []

        def handle(request: httpx2.Request) -> httpx2.Response:
            requests.append(request.url.path)
            return httpx2.Response(204)

        alert = Alert(bearish="no", symbol="SPX", alert="Alert", lastfired="")
        urls = [
            "https://discord.test:invalid/webhooks/first?token=first-secret",
            "https://discord.test/webhooks/second?token=second-secret",
        ]
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
            await send_alert_to_webhooks(client, alert, urls)

        assert requests == ["/webhooks/second"]

    with caplog.at_level(logging.ERROR):
        asyncio.run(scenario())
    assert "Discord webhook failed" in caplog.text
    assert "error=InvalidURL" in caplog.text
    assert "first-secret" not in caplog.text
    assert "second-secret" not in caplog.text
    assert "discord.test" not in caplog.text


def test_unexpected_delivery_error_propagates() -> None:
    """Propagate unexpected errors without trying later webhook URLs."""

    async def scenario() -> None:
        requests: list[str] = []

        def fail_unexpectedly(request: httpx2.Request) -> httpx2.Response:
            requests.append(request.url.path)
            raise RuntimeError("unexpected programming failure")

        alert = Alert(bearish="no", symbol="SPX", alert="Alert", lastfired="")
        urls = ["https://discord.test/webhooks/first", "https://discord.test/webhooks/second"]
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(fail_unexpectedly)) as client:
            with pytest.raises(RuntimeError, match="unexpected programming failure"):
                await send_alert_to_webhooks(client, alert, urls)

        assert requests == ["/webhooks/first"]

    asyncio.run(scenario())


def test_webhook_timeout_during_body_read_is_sanitized_and_delivery_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sanitize body-read timeouts and continue delivery."""

    async def scenario() -> None:
        requests: list[str] = []
        body_reads = 0
        body_read_started = asyncio.Event()
        body_stream_closed = asyncio.Event()

        class HangingBody(httpx2.AsyncByteStream):
            async def __aiter__(self) -> AsyncIterator[bytes]:
                nonlocal body_reads
                yield b"pending"
                body_reads += 1
                body_read_started.set()
                await asyncio.Future()

            async def aclose(self) -> None:
                body_stream_closed.set()

        def handle(request: httpx2.Request) -> httpx2.Response:
            requests.append(request.url.path)
            if request.url.path.endswith("first"):
                return httpx2.Response(200, stream=HangingBody())
            return httpx2.Response(204)

        alert = Alert(
            bearish="yes",
            symbol="$SPX",
            alert="Test alert",
            lastfired="31 Jul 2024, 12:33pm",
        )
        urls = [
            "https://discord.test/webhooks/first?token=first-secret",
            "https://discord.test/webhooks/second?token=second-secret",
        ]
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
            delivery_task = asyncio.create_task(send_alert_to_webhooks(client, alert, urls, request_timeout=0.0))
            watchdog = asyncio.timeout(1.0)
            try:
                async with watchdog:
                    await body_read_started.wait()
                    await asyncio.shield(delivery_task)
            except TimeoutError:
                if not watchdog.expired():
                    raise
                delivery_task.cancel()
                with suppress(asyncio.CancelledError):
                    await delivery_task
                if body_read_started.is_set() and not body_stream_closed.is_set():
                    raise AssertionError("watchdog cancellation left the response stream open") from None
                raise AssertionError("delivery exceeded the test watchdog") from None
            finally:
                if not delivery_task.done():
                    delivery_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await delivery_task

        assert requests == ["/webhooks/first", "/webhooks/second"]
        assert body_reads == 1
        assert body_stream_closed.is_set()

    with caplog.at_level(logging.ERROR):
        asyncio.run(scenario())
    assert "Discord webhook failed" in caplog.text
    assert "error=TimeoutError" in caplog.text
    assert "first-secret" not in caplog.text
    assert "second-secret" not in caplog.text
    assert "discord.test" not in caplog.text


def test_webhook_request_propagates_cancellation() -> None:
    """Propagate request cancellation without starting later webhook calls."""

    async def scenario() -> None:
        started = asyncio.Event()
        requests: list[str] = []

        async def hold_request(request: httpx2.Request) -> httpx2.Response:
            requests.append(request.url.path)
            started.set()
            await asyncio.Future()
            raise AssertionError("unreachable")

        alert = Alert(bearish="no", symbol="SPX", alert="Alert", lastfired="")
        urls = ["https://discord.test/webhooks/first", "https://discord.test/webhooks/second"]
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(hold_request)) as client:
            task = asyncio.create_task(send_alert_to_webhooks(client, alert, urls))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        assert requests == ["/webhooks/first"]

    asyncio.run(scenario())
