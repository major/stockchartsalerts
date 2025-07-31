#!/usr/bin/env python
"""Run the alert bot."""

import logging
from time import sleep

from schedule import every, repeat, run_pending

from stockchartsalerts import bot
from stockchartsalerts.config import MINUTES_BETWEEN_RUNS


@repeat(every(MINUTES_BETWEEN_RUNS).minutes)
def send_alerts() -> None:
    """Send alerts to Discord."""
    alerts = bot.get_new_alerts()

    for alert in alerts:
        bot.send_alert_to_discord(alert)


def main() -> None:
    """Main function to run the bot."""
    logging.info("🚀 Running Alerts Bot")

    send_alerts()

    # Run the schedule loop.
    while True:
        run_pending()
        sleep(1)


if __name__ == "__main__":
    main()
