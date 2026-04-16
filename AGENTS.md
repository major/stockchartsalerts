# AGENTS.md

> Authoritative knowledge base for AI agents. Keep this file updated when substantial changes land (new modules, config changes, CI updates, dependency shifts).

## Project

StockCharts Alerts Bot: polls stockcharts.com predefined alerts, sends new ones to Discord webhooks. Runs as a scheduled loop in a container.

- Python 3.14, uv package manager, `uv.lock` for reproducibility
- Entry point: `python -m stockchartsalerts.run_bot`
- Container: `ghcr.io/major/stockchartsalerts:latest`

## Directory Layout

```text
src/stockchartsalerts/
  __init__.py     # loguru config (import-time side effect)
  bot.py          # fetch alerts, filter new, send to Discord
  config.py       # pydantic-settings singleton, env/CLI parsing
  models.py       # Alert pydantic model
  run_bot.py      # scheduler loop, Sentry init, signal handling
tests/
  test_bot.py     # 20 tests - bot logic
  test_config.py  # 12 tests - config validation
```

## Architecture

### Config (`config.py`)

Pydantic Settings singleton accessed via `get_settings()`. Supports `.env` file and CLI args (`CliSettings`).

- `_settings` module-level singleton, reset to `None` between tests
- `discord_webhook_url` (deprecated) vs `discord_webhook_urls` (comma-separated, preferred)
- Deduplication of webhook URLs happens at config validation time
- Env vars: `DISCORD_WEBHOOK_URL`, `DISCORD_WEBHOOK_URLS`, `MINUTES_BETWEEN_RUNS` (1-1440, default 5), `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `GIT_COMMIT`, `GIT_BRANCH`

### HTTP Client (`bot.py`)

Persistent `_http_client` (httpx.Client) with connection pool limits (max_connections=10, max_keepalive=5). Created lazily, closed via `cleanup()`.

**Memory leak history**: prior versions used `httpx.get()` in loops, creating a new client per request, causing OOMKilled in production.

### Alert Flow

1. `get_alerts()` - fetches JSON from stockcharts.com, retries 3x (tenacity, exponential 2-10s)
2. `get_new_alerts()` - filters to alerts newer than last run time (Eastern TZ comparison)
3. `send_alert_to_discord()` - sends formatted embed to all configured webhooks
4. On failure at any step: log error, return empty list, continue loop

### Scheduler (`run_bot.py`)

`schedule` library runs `get_new_alerts()` + `send_alert_to_discord()` every N minutes. Error backoff: after 5 consecutive errors, waits 5 minutes instead of normal 1 minute between cycles.

## Critical Constraints

1. **Timezone**: StockCharts uses Eastern Time (America/New_York). ALL timestamp parsing MUST use ET context. Using UTC or naive datetimes will silently miss or duplicate alerts.

2. **HTTP client**: NEVER use `httpx.get()` or create new `httpx.Client()` instances in loops. Always use the persistent `_http_client`. This was a production memory leak.

3. **Webhook config**: `discord_webhook_url` (singular) is deprecated. New code should use `discord_webhook_urls`. At least one URL must be configured or Settings raises `ValueError`.

4. **Cleanup**: `bot.cleanup()` must be called on shutdown to close the HTTP client connection pool.

5. **Error resilience**: Functions must not raise on transient failures. Return empty list/None and log. The scheduler handles retry timing.

## Testing

Run: `make all` (lint + test + typecheck) or `make test` for tests only.

### Patterns

- **Settings fixture**: autouse `mock_settings` resets `_settings` singleton, sets env vars via `monkeypatch`, constructs `Settings(_env_file=None)` to skip `.env` loading
- **HTTP mocking**: `pytest-httpx` fixture `httpx_mock` with `add_response(url=..., json=...)` and `add_exception(httpx.TimeoutException(...))`
- **Time freezing**: `@freezegun.freeze_time("2024-07-31 16:00:00")` decorator on time-dependent tests
- **Retry bypass**: `mock.patch.object(bot._fetch_alerts.retry, 'wait', wait_none())` to skip tenacity waits in tests
- **Test data**: module-level `SAMPLE_ALERTS` constant (list of alert dicts)
- **Naming**: `test_<function>_<scenario>`
- **Assertions**: verify graceful degradation (empty list on failure, no crashes), call counts on mocks, `pytest.raises` for validation errors

### Dev Dependencies

freezegun, pytest, pytest-cov, pytest-httpx, pytest-randomly, ruff, pyright, pre-commit

## CI/CD

GitHub Actions (`.github/workflows/main.yml`), two jobs:

1. **testing**: setup python from `.python-version`, install uv 0.11.7, `uv sync`, `make all`
2. **container** (depends on testing, main branch only): build+push to GHCR, then checkout `major/selfhosted` repo and update deployment.yaml with new image digest

All actions pinned to SHA256 digests. Secrets: `GITHUB_TOKEN`, `SELFHOSTED_PAT`.

## Tooling

| Tool | Config | Command |
|------|--------|---------|
| ruff | `pyproject.toml` `[tool.ruff]` | `uv run ruff format --check` |
| pyright | `pyproject.toml` `[tool.pyright]` | `uv run pyright src/*` |
| pytest | `pyproject.toml` `[tool.pytest.ini_options]` | `uv run pytest` |
| pre-commit | `.pre-commit-config.yaml` | auto on commit |
| renovate | `renovate.json` | auto-merge minor/patch deps |
| codecov | `codecov.yaml` | 90% coverage target |

## Code Style

- Type hints on all functions, pyright strict mode
- Ruff formatting with preview features enabled
- Loguru for logging (emoji-rich messages)
- Single-purpose functions, functional patterns
- PEP 257 docstrings
