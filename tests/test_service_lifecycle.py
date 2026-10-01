"""Behavior tests for service startup, shutdown, and shared client lifecycle."""

from __future__ import annotations

import asyncio
import logging
import os
import signal

import httpx2
import pytest

from stockchartsalerts.__main__ import async_main
from stockchartsalerts.httpx_client import create_http_client


def test_invalid_service_configuration_exits_without_logging_secrets_or_creating_a_client(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def unexpected_client_factory() -> httpx2.AsyncClient:
        raise AssertionError("invalid configuration must not create an HTTP client")

    caplog.set_level(logging.DEBUG, logger="httpx2")
    caplog.set_level(logging.DEBUG, logger="httpcore2")
    with caplog.at_level(logging.ERROR):
        result = asyncio.run(
            async_main(
                {
                    "DISCORD_WEBHOOK_URLS": "https://secret.test/hook",
                    "MINUTES_BETWEEN_RUNS": "0",
                },
                client_factory=unexpected_client_factory,
            )
        )

    assert result == 1
    assert "failed to load configuration" in caplog.text
    assert "secret.test" not in caplog.text


def test_client_startup_failure_logs_only_the_exception_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail_client_factory() -> httpx2.AsyncClient:
        raise RuntimeError("failed for https://discord.test/webhook/token-secret")

    caplog.set_level(logging.DEBUG, logger="httpx2")
    caplog.set_level(logging.DEBUG, logger="httpcore2")
    with caplog.at_level(logging.ERROR):
        result = asyncio.run(
            async_main(
                {"DISCORD_WEBHOOK_URLS": "https://discord.test/webhook/token-secret"},
                client_factory=fail_client_factory,
            )
        )

    assert result == 1
    assert "application failed" in caplog.text
    assert "error=RuntimeError" in caplog.text
    assert "discord.test" not in caplog.text
    assert "token-secret" not in caplog.text


def test_sigterm_cancels_poll_and_closes_the_shared_client(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def scenario() -> None:
        request_started = asyncio.Event()
        clients: list[httpx2.AsyncClient] = []

        async def hold_request(request: httpx2.Request) -> httpx2.Response:
            assert request.url.host == "stockcharts.com"
            request_started.set()
            await asyncio.Future()

        def create_client() -> httpx2.AsyncClient:
            client = httpx2.AsyncClient(transport=httpx2.MockTransport(hold_request))
            clients.append(client)
            return client

        task = asyncio.create_task(
            async_main(
                {
                    "DISCORD_WEBHOOK_URLS": "https://discord.test/webhook",
                    "GIT_BRANCH": "release",
                    "GIT_COMMIT": "abc123",
                },
                client_factory=create_client,
            )
        )
        await request_started.wait()
        os.kill(os.getpid(), signal.SIGTERM)

        assert await task == 0
        assert len(clients) == 1
        assert clients[0].is_closed

    caplog.set_level(logging.DEBUG, logger="httpx2")
    caplog.set_level(logging.DEBUG, logger="httpcore2")
    with caplog.at_level(logging.INFO):
        asyncio.run(scenario())

    assert "release@abc123" in caplog.text
    assert "shutdown signal received; exiting" in caplog.text


def test_shared_client_exposes_the_service_timeout_and_redirect_policy() -> None:
    async def scenario() -> None:
        async with create_http_client() as client:
            assert client.timeout == httpx2.Timeout(30.0)
            assert client.follow_redirects
            assert client.max_redirects == 10

    asyncio.run(scenario())
