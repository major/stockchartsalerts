"""Top level package."""

import logging
import sys

import sentry_sdk

from stockchartsalerts.config import settings

# Initialize Sentry if DSN is provided
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        release=f"{settings.git_branch}@{settings.git_commit}",
        # Set traces_sample_rate to 1.0 to capture 100% of transactions for tracing
        # We recommend adjusting this value in production
        traces_sample_rate=0.1,
        # Capture 100% of errors
        profiles_sample_rate=1.0,
    )

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s;%(levelname)s;%(message)s",
)
