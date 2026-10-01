"""Pure environment-settings normalization and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

_INTEGER = re.compile(r"[+-]?[0-9]+")
_LOG_LEVELS = frozenset({"debug", "info", "warn", "error"})
_MAX_MINUTES_BETWEEN_RUNS = 1440


@dataclass(frozen=True, slots=True, kw_only=True)
class Settings:
    """Validated runtime settings supplied to the application."""

    webhook_urls: tuple[str, ...]
    minutes_between_runs: int
    git_commit: str
    git_branch: str
    log_level: str


def load_settings(env: Mapping[str, str]) -> Settings:
    """Normalize settings from a mapping, without reading process environment."""
    if "MINUTES_BETWEEN_RUNS" in env:
        raw_minutes = env["MINUTES_BETWEEN_RUNS"]
        if not isinstance(raw_minutes, str) or _INTEGER.fullmatch(raw_minutes) is None:
            raise ValueError("MINUTES_BETWEEN_RUNS must be a valid integer")
        minutes_between_runs = int(raw_minutes)
    else:
        minutes_between_runs = 5

    if not 1 <= minutes_between_runs <= _MAX_MINUTES_BETWEEN_RUNS:
        raise ValueError(f"MINUTES_BETWEEN_RUNS must be between 1 and {_MAX_MINUTES_BETWEEN_RUNS}")

    raw_webhook_urls = env.get("DISCORD_WEBHOOK_URLS", "")
    if not isinstance(raw_webhook_urls, str):
        raise ValueError("at least one Discord webhook URL must be provided via DISCORD_WEBHOOK_URLS")

    webhook_urls: list[str] = []
    seen: set[str] = set()
    for url in raw_webhook_urls.split(","):
        normalized_url = url.strip()
        if normalized_url and normalized_url not in seen:
            seen.add(normalized_url)
            webhook_urls.append(normalized_url)
    if not webhook_urls:
        raise ValueError("at least one Discord webhook URL must be provided via DISCORD_WEBHOOK_URLS")

    git_commit = env.get("GIT_COMMIT", "unknown").strip() or "unknown"
    git_branch = env.get("GIT_BRANCH", "unknown").strip() or "unknown"
    log_level = env.get("LOG_LEVEL", "info").strip().lower()
    if log_level not in _LOG_LEVELS:
        log_level = "info"

    return Settings(
        webhook_urls=tuple(webhook_urls),
        minutes_between_runs=minutes_between_runs,
        git_commit=git_commit,
        git_branch=git_branch,
        log_level=log_level,
    )
