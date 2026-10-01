"""Process entry point for the StockCharts alerts polling service."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    import httpx2

from stockchartsalerts.app import App
from stockchartsalerts.config import load_settings
from stockchartsalerts.httpx_client import create_http_client
from stockchartsalerts.telemetry import configure_logging

logger = logging.getLogger(__name__)


async def async_main(
    env: Mapping[str, str] | None = None,
    *,
    client_factory: Callable[[], httpx2.AsyncClient] = create_http_client,
) -> int:
    """Load settings and run the service until it is cancelled."""
    environment = os.environ if env is None else env
    configure_logging(environment.get("LOG_LEVEL", "info"))

    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    registered_signals: list[signal.Signals] = []
    if task is not None:
        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(signum, task.cancel)
            except NotImplementedError, RuntimeError:
                continue
            registered_signals.append(signum)

    try:
        try:
            settings = load_settings(environment)
        except ValueError:
            # Configuration errors can contain webhook values, so do not log
            # their exception text.
            logger.error("failed to load configuration")  # noqa: TRY400
            return 1

        configure_logging(settings.log_level)
        logger.info(
            "=== Starting StockCharts Alerts ===\nBranch: %s\nCommit: %s\n====================================",
            settings.git_branch,
            settings.git_commit,
        )

        async with client_factory() as client:
            application = App(settings, client)
            await application.run()
    except asyncio.CancelledError:
        logger.info("shutdown signal received; exiting")
        return 0
    except Exception as error:  # noqa: BLE001
        # Integration errors are sanitized at their boundaries. Avoid logging
        # arbitrary exception details here in case a third-party error includes
        # a configured URL.
        # Do not attach a traceback that could expose the underlying exception.
        logger.error("application failed; error=%s", type(error).__name__)  # noqa: TRY400
        return 1
    finally:
        for signum in registered_signals:
            loop.remove_signal_handler(signum)

    return 0


def main() -> None:
    """Run the async service and return its status through the process exit code."""
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
