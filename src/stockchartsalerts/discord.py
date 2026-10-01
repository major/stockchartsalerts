"""Discord payload formatting and best-effort webhook delivery."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx2

from stockchartsalerts.httpx_client import REQUEST_TIMEOUT_SECONDS

if TYPE_CHECKING:
    from collections.abc import Sequence

    from stockchartsalerts.alerts import Alert

logger = logging.getLogger(__name__)
_AVATAR_URL = "https://emojiguide.org/images/emoji/1/8z8e40kucdd1.png"
_DOW_PREFIX = "Dow crosses above "


def make_payload(alert: Alert) -> dict[str, str]:
    """Format an alert as the fixed Discord webhook JSON payload."""
    emoji = "🔴" if alert.bearish == "yes" else "💚"
    message = alert.alert
    if message.startswith(_DOW_PREFIX):
        message = f"THE DOW, THE DOW IS ABOVE {message.removeprefix(_DOW_PREFIX)}"

    return {
        "username": alert.symbol,
        "avatar_url": _AVATAR_URL,
        "content": f"{emoji}  {message}",
    }


async def send_alert_to_webhooks(
    client: httpx2.AsyncClient,
    alert: Alert,
    urls: Sequence[str],
    *,
    request_timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> None:
    """Post to each webhook in order, logging sanitized errors and continuing."""
    payload = make_payload(alert)
    total = len(urls)

    for index, url in enumerate(urls, start=1):
        try:
            async with asyncio.timeout(request_timeout):
                response = await client.post(url, json=payload)
        except (httpx2.HTTPError, httpx2.InvalidURL, TimeoutError, ValueError) as error:
            # Request errors may contain webhook URLs or credentials; omit tracebacks.
            logger.error(  # noqa: TRY400
                "Discord webhook failed; webhook=%d/%d error=%s symbol=%s",
                index,
                total,
                type(error).__name__,
                alert.symbol,
            )
            continue

        if response.is_success:
            logger.info("alert sent to Discord; webhook=%d/%d symbol=%s", index, total, alert.symbol)
        else:
            logger.error(
                "Discord webhook failed; webhook=%d/%d status=%d symbol=%s",
                index,
                total,
                response.status_code,
                alert.symbol,
            )
