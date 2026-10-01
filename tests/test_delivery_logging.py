"""Delivery diagnostic fields and best-effort behavior."""

from __future__ import annotations

import asyncio
import logging

import httpx2
import pytest

from stockchartsalerts.alerts import Alert
from stockchartsalerts.discord import send_alert_to_webhooks


def test_delivery_diagnostics_are_sanitized_and_cover_each_webhook(
    caplog: pytest.LogCaptureFixture,
) -> None:
    urls = (
        "https://webhook-host.invalid/hooks/success-first?token=secret-one",
        "https://webhook-host.invalid/hooks/status-first?token=secret-two",
        "https://webhook-host.invalid/hooks/transport-first?token=secret-three",
        "https://webhook-host.invalid/hooks/success-later?token=secret-four",
        "https://webhook-host.invalid/hooks/status-later?token=secret-five",
        "https://webhook-host.invalid/hooks/transport-later?token=secret-six",
    )

    async def scenario() -> None:
        requests: list[str] = []
        active_requests = 0
        maximum_active_requests = 0
        response_statuses = {
            "/hooks/success-first": 204,
            "/hooks/status-first": 503,
            "/hooks/success-later": 202,
            "/hooks/status-later": 429,
        }
        transport_failures = {"/hooks/transport-first", "/hooks/transport-later"}

        async def handle(request: httpx2.Request) -> httpx2.Response:
            nonlocal active_requests, maximum_active_requests
            requests.append(request.url.path)
            active_requests += 1
            maximum_active_requests = max(maximum_active_requests, active_requests)
            try:
                await asyncio.sleep(0)
                if request.url.path in transport_failures:
                    raise httpx2.ConnectError(
                        "upstream failed with private transport detail",
                        request=request,
                    )
                return httpx2.Response(response_statuses[request.url.path])
            finally:
                active_requests -= 1

        alert = Alert(
            bearish="no",
            symbol="NASDAQ",
            alert="Test alert",
            lastfired="31 Jul 2024, 12:33pm",
        )
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
            await send_alert_to_webhooks(client, alert, urls)

        assert requests == [
            "/hooks/success-first",
            "/hooks/status-first",
            "/hooks/transport-first",
            "/hooks/success-later",
            "/hooks/status-later",
            "/hooks/transport-later",
        ]
        assert maximum_active_requests == 1

    with caplog.at_level(logging.INFO, logger="stockchartsalerts.discord"):
        asyncio.run(scenario())

    records = [record for record in caplog.records if record.name == "stockchartsalerts.discord"]
    expected_diagnostics = [
        (logging.INFO, ("webhook=1/6", "symbol=NASDAQ")),
        (logging.ERROR, ("webhook=2/6", "status=503", "symbol=NASDAQ")),
        (logging.ERROR, ("webhook=3/6", "error=ConnectError", "symbol=NASDAQ")),
        (logging.INFO, ("webhook=4/6", "symbol=NASDAQ")),
        (logging.ERROR, ("webhook=5/6", "status=429", "symbol=NASDAQ")),
        (logging.ERROR, ("webhook=6/6", "error=ConnectError", "symbol=NASDAQ")),
    ]
    assert len(records) == len(expected_diagnostics)
    for record, (level, fields) in zip(records, expected_diagnostics, strict=True):
        message = record.getMessage()
        assert record.levelno == level
        assert all(field in message for field in fields)

    for secret in (
        "webhook-host.invalid",
        "secret-one",
        "secret-two",
        "secret-three",
        "secret-four",
        "secret-five",
        "secret-six",
        "private transport detail",
    ):
        assert secret not in caplog.text
    assert all(url not in caplog.text for url in urls)
