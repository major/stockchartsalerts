"""Configuration settings."""

import logging
import os

log = logging.getLogger(__name__)

MINUTES_BETWEEN_RUNS: int = int(os.getenv("MINUTES_BETWEEN_RUNS", 5))

# Discord Channels
DISCORD_WEBHOOK: str = os.getenv("DISCORD_WEBHOOK", "missing")

# Sentry Configuration
SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
SENTRY_ENVIRONMENT: str = os.getenv("SENTRY_ENVIRONMENT", "production")

# Git Version Info (set at build time)
GIT_COMMIT: str = os.getenv("GIT_COMMIT", "unknown")
GIT_BRANCH: str = os.getenv("GIT_BRANCH", "unknown")
