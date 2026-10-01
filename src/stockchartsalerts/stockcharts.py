"""HTTP fetching and retry behavior for StockCharts alerts."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import cast

import httpx

from stockchartsalerts.httpx_client import REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://stockcharts.com/j-sum/sum?cmd=alert"
_REFERER = "https://stockcharts.com/freecharts/alertsummary.html"
_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0"
_RETRY_DELAYS = (2.0, 4.0)
Sleep = Callable[[float], Awaitable[None]]


class FetchError(Exception):
    """A sanitized error raised when StockCharts data cannot be fetched."""


async def fetch_alerts(
    client: httpx.AsyncClient,
    *,
    sleep: Sleep = asyncio.sleep,
    endpoint: str = DEFAULT_ENDPOINT,
    request_timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> list[object]:
    """Fetch and decode the StockCharts alert array with bounded retries."""
    for attempt in range(len(_RETRY_DELAYS) + 1):
        try:
            return await _fetch_once(client, endpoint, request_timeout)
        except FetchError:
            if attempt == len(_RETRY_DELAYS):
                raise

            logger.warning("StockCharts fetch failed; retrying attempt=%d", attempt + 1)
            await sleep(_RETRY_DELAYS[attempt])

    raise AssertionError("unreachable retry state")


async def _fetch_once(
    client: httpx.AsyncClient,
    endpoint: str,
    request_timeout: float,
) -> list[object]:
    try:
        async with asyncio.timeout(request_timeout):
            response = await client.get(
                endpoint,
                headers={"Referer": _REFERER, "User-Agent": _USER_AGENT},
            )
    except httpx.HTTPError, TimeoutError, ValueError:
        raise FetchError("StockCharts request failed") from None

    if not 200 <= response.status_code < 300:
        raise FetchError(f"StockCharts returned HTTP status {response.status_code}")

    try:
        payload = response.json()
    except ValueError:
        raise FetchError("StockCharts response was not valid JSON") from None

    if not isinstance(payload, list):
        raise FetchError("StockCharts response was not a JSON array")

    return cast(list[object], payload)
