# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🎯 Project Overview

**StockCharts Alerts Bot** - A Python bot that polls [StockCharts.com predefined alerts](https://stockcharts.com/freecharts/alertsummary.html) and sends notifications to Discord webhook(s) when new market alerts are detected.

## 🏗️ Architecture

### Core Components

- **`bot.py`**: Core alert fetching and delivery logic
  - `get_alerts()`: Fetches alerts from stockcharts.com with retry logic (3 attempts, exponential backoff)
  - `get_new_alerts()`: Filters alerts to only those newer than the last run (based on Eastern timezone)
  - `send_alert_to_discord()`: Sends alerts to all configured Discord webhooks
  - Uses tenacity for automatic retries on HTTP errors

- **`config.py`**: Pydantic-based configuration management
  - Environment variable loading from `.env` file
  - Supports multiple Discord webhooks (comma-separated via `DISCORD_WEBHOOK_URLS`)
  - Backward compatible with legacy single `DISCORD_WEBHOOK_URL`
  - Sentry integration for error tracking
  - Git version info injection at build time

- **`run_bot.py`**: Main entry point and scheduler
  - Uses `schedule` library to run checks every N minutes (configurable via `MINUTES_BETWEEN_RUNS`)
  - Includes error resilience: backs off for 5 minutes after 5 consecutive errors
  - Initializes Sentry with git version info for release tracking

### Time Zone Handling

⏰ **CRITICAL**: StockCharts uses Eastern Time (America/New_York). All alert timestamps must be parsed with Eastern timezone context to correctly filter new alerts.

### Error Handling Strategy

🛡️ The bot is designed to be resilient:
- HTTP requests retry 3x with exponential backoff (2s min, 10s max)
- On failure, returns empty list rather than crashing
- Scheduler handles exceptions and backs off on consecutive errors
- Sentry integration captures all exceptions for monitoring

## 🔧 Development Commands

### Environment Setup
```bash
# Install dependencies (uses uv package manager)
uv sync --locked --all-extras --dev
```

### Running Tests
```bash
# Run all checks (lint, test, typecheck)
make all

# Individual commands
uv run pytest              # Tests with coverage
uv run ruff format --check # Linting
uv run pyright src/*       # Type checking
```

### Running the Bot Locally
```bash
# Requires environment variables in .env:
# - DISCORD_WEBHOOK_URL or DISCORD_WEBHOOK_URLS
# - Optional: SENTRY_DSN, MINUTES_BETWEEN_RUNS (default: 5)
uv run python src/stockchartsalerts/run_bot.py
```

### Running Single Tests
```bash
# Run specific test file
uv run pytest tests/test_bot.py

# Run specific test function
uv run pytest tests/test_bot.py::test_function_name

# Run with verbose output
uv run pytest -vv tests/test_bot.py
```

## 🧪 Testing

- **Framework**: pytest with extensive configuration in `pyproject.toml`
- **Coverage**: Enforced via `pytest-cov` (reports to terminal, HTML, and XML)
- **Test Utilities**:
  - `pytest-httpx`: Mock HTTP requests to stockcharts.com
  - `freezegun`: Time travel for testing time-based logic
  - `pytest-randomly`: Randomize test order to catch state dependencies

## 📦 Container Build

The project uses a Dockerfile (not Containerfile yet) with:
- Multi-stage build injecting git version info via build args
- Pushes to `ghcr.io/major/stockchartsalerts:latest` on main branch
- Auto-updates deployment manifest in private `major/selfhosted` repo

## 🔑 Environment Variables

Required:
- `DISCORD_WEBHOOK_URL` OR `DISCORD_WEBHOOK_URLS` (comma-separated for multiple)

Optional:
- `MINUTES_BETWEEN_RUNS` (default: 5, range: 1-1440)
- `SENTRY_DSN` (error tracking)
- `SENTRY_ENVIRONMENT` (default: "production")
- `GIT_COMMIT` / `GIT_BRANCH` (set at build time)

## 📝 Code Style

- Type hints required on all functions
- Uses Ruff for formatting (auto-fix enabled)
- Pyright for static type checking (strict mode)
- Loguru for logging with emoji-rich messages 🎨
- Follow functional patterns: pure functions, single responsibility
