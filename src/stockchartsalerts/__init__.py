"""Top level package."""

import logging
import sys

import sentry_sdk

from stockchartsalerts.config import (
    GIT_BRANCH,
    GIT_COMMIT,
    SENTRY_DSN,
    SENTRY_ENVIRONMENT,
)

# Initialize Sentry if DSN is provided
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        release=f"{GIT_BRANCH}@{GIT_COMMIT}",
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
