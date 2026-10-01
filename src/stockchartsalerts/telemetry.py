"""Logging setup for the command and application."""

from __future__ import annotations

import logging
import sys

_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "error": logging.ERROR,
}


def configure_logging(log_level: str) -> str:
    """Configure plain-text logging and return the normalized level name."""
    normalized = log_level.strip().lower()
    if normalized not in _LEVELS:
        normalized = "info"

    root_logger = logging.getLogger()
    root_logger.setLevel(_LEVELS[normalized])
    for library_logger in ("httpx2", "httpcore2"):
        logging.getLogger(library_logger).setLevel(logging.WARNING)

    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root_logger.addHandler(handler)

    return normalized
