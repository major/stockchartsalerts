"""Configuration settings."""

import logging
import os

log = logging.getLogger(__name__)

MINUTES_BETWEEN_RUNS: int = int(os.getenv("MINUTES_BETWEEN_RUNS", 5))

# Discord Channels
DISCORD_WEBHOOK: str = os.getenv("DISCORD_WEBHOOK", "missing")
