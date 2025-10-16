#!/usr/bin/env python
"""Run the alert bot."""

from time import sleep

from loguru import logger
from schedule import every, repeat, run_pending

from stockchartsalerts import bot
from stockchartsalerts.config import settings


@repeat(every(settings.minutes_between_runs).minutes)
def send_alerts() -> None:
    """Send alerts to Discord."""
    alerts = bot.get_new_alerts()

    for alert in alerts:
        bot.send_alert_to_discord(alert)


def main() -> None:
    """Main function to run the bot."""
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
