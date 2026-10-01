"""HTTP fetching and retry behavior for StockCharts alerts."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import cast

import httpx2

from stockchartsalerts.httpx_client import REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://stockcharts.com/j-sum/sum?cmd=alert"
_REFERER = "https://stockcharts.com/freecharts/alertsummary.html"
_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0"
_RETRY_DELAYS = (2.0, 4.0)
Sleep = Callable[[float], Awaitable[None]]


class FetchError(Exception):
    """A sanitized error raised when StockCharts data cannot be fetched."""


class _RequestFailedError(FetchError):
    def __init__(self) -> None:
        super().__init__("StockCharts request failed")


class _HttpStatusError(FetchError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"StockCharts returned HTTP status {status_code}")


class _InvalidJsonError(FetchError):
    def __init__(self) -> None:
        super().__init__("StockCharts response was not valid JSON")


class _NonArrayResponseError(FetchError):
    def __init__(self) -> None:
        super().__init__("StockCharts response was not a JSON array")


class _UnreachableRetryStateError(AssertionError):
    def __init__(self) -> None:
        super().__init__("unreachable retry state")


async def fetch_alerts(
    client: httpx2.AsyncClient,
    *,
    sleep: Sleep = asyncio.sleep,
    endpoint: str = DEFAULT_ENDPOINT,
    request_timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> list[object]:
    """Fetch and decode the StockCharts alert array with bounded retries."""
    for attempt in range(len(_RETRY_DELAYS) + 1):
        try:
            return await _fetch_once(client, endpoint, request_timeout)
        except FetchError as error:
            if attempt == len(_RETRY_DELAYS):
                raise

            logger.warning("StockCharts fetch failed; %s; retrying attempt=%d", error, attempt + 1)
            await sleep(_RETRY_DELAYS[attempt])

    raise _UnreachableRetryStateError()


async def _fetch_once(
    client: httpx2.AsyncClient,
    endpoint: str,
    request_timeout: float,
) -> list[object]:
    try:
        async with asyncio.timeout(request_timeout):
            response = await client.get(
                endpoint,
                headers={"Referer": _REFERER, "User-Agent": _USER_AGENT},
            )
    except httpx2.HTTPError, TimeoutError, ValueError:
        raise _RequestFailedError from None

    if not HTTPStatus.OK <= response.status_code < HTTPStatus.MULTIPLE_CHOICES:
        raise _HttpStatusError(response.status_code)

    try:
        payload = response.json()
    except ValueError:
        raise _InvalidJsonError from None

    if not isinstance(payload, list):
        raise _NonArrayResponseError

    return cast("list[object]", payload)
