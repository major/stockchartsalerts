# Repository Atlas: StockCharts Alerts Bot

## Project Responsibility

This Python service polls StockCharts' predefined-alert endpoint, identifies
alerts newer than its in-memory lookback anchor in Eastern Time, and posts each
result to configured Discord webhooks. It is an async, signal-aware process
with bounded fetch retries and scheduler backoff.

## System Entry Points

- `pyproject.toml`: Python project metadata, dependencies, tooling settings, and
  the `stockchartsalerts` console script.
- `uv.lock`: Locked dependency resolution used by `uv sync --locked`.
- `src/stockchartsalerts/__main__.py`: Package command entry point.
- `src/stockchartsalerts/app.py`: Async polling orchestration, shared client
  lifecycle, lookback anchor, scheduler, backoff, and signal cancellation.
- `Makefile`: Formatting, linting, type checking, tests, branch coverage, build,
  and dependency audit commands.

## Primary Alert Flow

1. `__main__` initializes plain-text logging, loads validated environment
   settings, and starts the async application.
2. `app` creates one shared asynchronous `httpx` client, performs one startup
   check, then schedules recurring checks and responds to SIGINT or SIGTERM.
3. `stockcharts` fetches and decodes the StockCharts response with bounded
   retries. `alerts` normalizes and selects rows, parses timestamps in
   `America/New_York`, and counts malformed rows and invalid timestamps.
4. `alerts` keeps only rows strictly newer than the lookback anchor and the
   latest timestamp or tied timestamps for each case-sensitive symbol.
5. `discord` builds the fixed webhook payload and posts sequentially to every
   configured webhook on a best-effort basis. A successful fetch advances the
   in-memory anchor even if a webhook post fails.

## Repository Directory Map

| Directory | Responsibility summary | Detailed map |
| --- | --- | --- |
| `src/stockchartsalerts/` | Python package and console entry point. | [Package modules below](#package-modules) |
| `tests/` | Sociable tests organized by behavior. | Alert selection, configuration, polling, service lifecycle, delivery, and feed recovery. |
| `docs/` | User-facing behavior contracts and operational details. | [docs/behaviors.md](docs/behaviors.md) |

## Package Modules

| Module | Responsibility |
| --- | --- |
| `__main__.py` | Console entry point and process startup. |
| `app.py` | Polling, aggregate rejection warnings, shared async client lifecycle, in-memory lookback state, scheduler, backoff, and graceful cancellation. |
| `config.py` | Environment parsing, normalization, defaults, and validation. |
| `alerts.py` | Alert row defaults, filtering, timestamp parsing, latest-per-symbol selection, and aggregate rejection counts. |
| `stockcharts.py` | StockCharts HTTP request, response decoding, and fetch retries. |
| `discord.py` | Discord payload formatting and sequential best-effort delivery. |
| `httpx_client.py` | Shared async HTTP client defaults and response status checks. |
| `telemetry.py` | Plain-text logging setup and log level selection. |

## Operational Constraints

- All StockCharts timestamps use `America/New_York`.
- `DISCORD_WEBHOOK_URLS` is the only supported webhook setting.
- The shared async `httpx` client is created at application startup, reused for
  both integrations, and closed at shutdown. Do not create clients in the poll
  loop.
- SIGINT and SIGTERM cancel the async polling work and allow client cleanup.
- StockCharts fetch failures and individual Discord delivery failures are
  handled without crashing the service where possible.
- Rejected feed rows produce one aggregate warning per poll with counts only,
  without logging row values, symbols, timestamps, or exception details.
- Polling progress is in memory only. There is no durable watermark, Discord
  retry, or guaranteed delivery.
