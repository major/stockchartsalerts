#!/usr/bin/env python
"""Run the alert bot."""

import logging
from time import sleep

from schedule import every, repeat, run_pending

from stockchartsalerts import bot
from stockchartsalerts.config import GIT_BRANCH, GIT_COMMIT, MINUTES_BETWEEN_RUNS


@repeat(every(MINUTES_BETWEEN_RUNS).minutes)
def send_alerts() -> None:
    """Send alerts to Discord."""
    alerts = bot.get_new_alerts()

    for alert in alerts:
        bot.send_alert_to_discord(alert)


def main() -> None:
    """Main function to run the bot."""
    logging.info("🚀 Running Alerts Bot")
    logging.info(f"📦 Version: {GIT_BRANCH}@{GIT_COMMIT}")

    # Run initial alerts check
    try:
        send_alerts()
    except Exception as e:
        logging.error(f"Error during initial alert check: {e}", exc_info=True)

    # Run the schedule loop with error protection
    consecutive_errors = 0
    max_consecutive_errors = 5

    while True:
        try:
            run_pending()
            consecutive_errors = 0  # Reset on success
            sleep(1)
        except KeyboardInterrupt:
            logging.info("⏹️  Shutting down gracefully...")
            break
        except Exception as e:
            consecutive_errors += 1
            logging.error(
                f"Error in scheduler loop (consecutive: {consecutive_errors}): {e}",
                exc_info=True,
            )

            # If too many consecutive errors, back off longer
            if consecutive_errors >= max_consecutive_errors:
                logging.warning(
                    f"⚠️  {consecutive_errors} consecutive errors, backing off for 5 minutes..."
                )
                sleep(300)  # 5 minute backoff
            else:
                sleep(60)  # 1 minute backoff on errors


if __name__ == "__main__":
    main()
