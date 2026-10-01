# AGENTS.md

> Authoritative working notes for agents. Keep this file current when substantial changes land.

## Project

StockCharts Alerts is a Python 3.14 or newer async service. It polls the
StockCharts predefined-alert feed and sends new alerts to configured Discord
webhooks.

- Package source: `src/stockchartsalerts/`.
- Console command: `stockchartsalerts`, configured by the project script in
  `pyproject.toml` and run with `uv run stockchartsalerts`.
- Dependencies and lock state are managed by `uv`; use `uv sync --locked`.
- Read [codemap.md](codemap.md) before changing architecture and
  [docs/behaviors.md](docs/behaviors.md) before changing observable behavior.

## Package Modules

- `__main__.py`: process entry point and startup.
- `config.py`: environment parsing, normalization, and validation.
- `alerts.py`: alert normalization, filtering, Eastern Time parsing, and
  latest-per-symbol selection.
- `stockcharts.py`: StockCharts async fetch, response decoding, and retries.
- `discord.py`: payload formatting and sequential best-effort webhook delivery.
- `httpx_client.py`: shared async HTTP client creation and status handling.
- `app.py`: polling orchestration, in-memory lookback state, scheduling,
  backoff, client lifecycle, and signal cancellation.
- `telemetry.py`: plain-text logging setup.

## Operational Contracts

- `DISCORD_WEBHOOK_URLS` is required and is the only supported webhook variable.
  Do not add support for singular `DISCORD_WEBHOOK_URL`.
- `MINUTES_BETWEEN_RUNS` defaults to 5, accepts integer text without surrounding
  whitespace, and must be between 1 and 1440 inclusive.
- `GIT_COMMIT` and `GIT_BRANCH` are optional startup-log labels and default to
  `unknown`.
- StockCharts timestamps must be interpreted in `America/New_York`, including
  daylight-saving transitions.
- Create one shared async `httpx` client during application startup. Reuse it
  for StockCharts and Discord requests, apply a 30-second timeout, and close it
  during shutdown. Never create clients inside the polling loop.
- Handle SIGINT and SIGTERM by cancelling the async work and cleaning up the
  shared client.
- StockCharts requests have three total attempts with 2-second and 4-second
  retry delays. The scheduler waits 60 seconds after a recurring failure, or
  300 seconds after five or more consecutive recurring failures. The initial
  startup failure does not count toward that consecutive-failure threshold.
- Discord delivery is best effort, sequential, and has no retry. A successful
  StockCharts fetch advances the in-memory lookback anchor even when delivery
  fails. There is no durable watermark or delivery guarantee.
- Logs are plain text, not JSON. There is no Sentry integration.

## Python and Test Practices

- Use Python 3.14 or newer and `uv` for environment and lockfile operations.
- Keep type annotations on functions and data crossing module boundaries, and
  satisfy the configured strict `mypy` and standard Pyright checks.
- Prefer small, typed helpers for pure parsing, filtering, and formatting rules.
- Test observable behavior through public package boundaries. For network
  behavior, use local test servers or injected clients at the HTTP boundary.
  Avoid mocks of internal helpers and implementation details.
- Cover important branches and failure paths, but do not change behavior or add
  contrived tests only to raise a coverage percentage.
- Use explicit `America/New_York` timestamps in time-sensitive tests. Do not
  depend on wall-clock time or the machine's local timezone.
- Tests are randomized with `pytest-randomly`. Reproduce a test order by passing
  the reported seed to `uv run --locked pytest --randomly-seed=<seed>`.

## Development Checks

```bash
uv sync --locked
make all
make audit
```

`make all` runs formatting, lint, type checking, branch coverage, and `uv build`.
The coverage target is the single test run in `make all`. The individual
Makefile targets are `fmt`, `lint`, `types`, `test`, `coverage`, and `build`.
`make audit` runs `pip-audit`.

## Documentation Maintenance

- Keep `codemap.md` aligned with package modules, data flow, and entry points.
- Keep `docs/behaviors.md` aligned with exact business and operational
  contracts, especially timestamps, filtering, Discord payloads, poll anchors,
  retries, and delivery limitations.
- Do not describe the legacy Go directory tree as the current application
  architecture. The Python package under `src/stockchartsalerts/` is current.
