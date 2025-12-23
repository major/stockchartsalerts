#!/usr/bin/env python
"""Run the alert bot."""

import atexit
from time import sleep

import sentry_sdk
from loguru import logger
from schedule import every, repeat, run_pending

from stockchartsalerts import bot
from stockchartsalerts.config import get_settings


@repeat(every(get_settings().minutes_between_runs).minutes)
def send_alerts() -> None:
    """Send alerts to Discord."""
    alerts = bot.get_new_alerts()

    for alert in alerts:
        bot.send_alert_to_discord(alert)


def main() -> None:
    """Main function to run the bot."""
    settings = get_settings()

    # Register cleanup handler to close HTTP client on shutdown.
    # This ensures we don't leak connection pools when the container stops.
    atexit.register(bot.cleanup)

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

    logger.info("🚀 Running Alerts Bot")
    logger.info(f"📦 Version: {settings.git_branch}@{settings.git_commit}")

    # Run initial alerts check
    try:
        send_alerts()
    except Exception as e:
        logger.exception(f"Error during initial alert check: {e}")

    # Run the schedule loop with error protection
    consecutive_errors = 0
    max_consecutive_errors = 5

    while True:
        try:
            run_pending()
            consecutive_errors = 0  # Reset on success
            sleep(1)
        except KeyboardInterrupt:
            logger.info("⏹️  Shutting down gracefully...")
            break
        except Exception as e:
            consecutive_errors += 1
            logger.exception(
                f"Error in scheduler loop (consecutive: {consecutive_errors}): {e}"
            )

            # If too many consecutive errors, back off longer
            if consecutive_errors >= max_consecutive_errors:
                logger.warning(
                    f"⚠️  {consecutive_errors} consecutive errors, backing off for 5 minutes..."
                )
                sleep(300)  # 5 minute backoff
            else:
                sleep(60)  # 1 minute backoff on errors


if __name__ == "__main__":
    main()
