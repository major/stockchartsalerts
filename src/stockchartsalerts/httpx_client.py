"""Shared asynchronous HTTP client configuration."""

from __future__ import annotations

import httpx2

REQUEST_TIMEOUT_SECONDS = 30.0


def create_http_client() -> httpx2.AsyncClient:
    """Create the shared client used for StockCharts and Discord requests."""
    return httpx2.AsyncClient(
        timeout=httpx2.Timeout(REQUEST_TIMEOUT_SECONDS),
        limits=httpx2.Limits(max_keepalive_connections=5, keepalive_expiry=30.0),
        follow_redirects=True,
        max_redirects=10,
    )
