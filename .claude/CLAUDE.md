# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StockCharts Alerts Bot is a Rust service that polls [StockCharts.com predefined alerts](https://stockcharts.com/freecharts/alertsummary.html) and sends new market alerts to Discord webhooks.

## Architecture

### Core Components

- `main.rs`: thin Tokio entry point.
- `lib.rs`: module tree and top-level `run()` function.
- `app.rs`: scheduler, startup poll, recurring interval, error backoff, and graceful shutdown.
- `alerts.rs`: alert model, placeholder filtering, Eastern Time timestamp parsing, and Discord text formatting.
- `config.rs`: clap/env settings normalization. Requires `DISCORD_WEBHOOK_URLS`; singular `DISCORD_WEBHOOK_URL` is unsupported.
- `discord.rs`: Discord webhook payloads and delivery to all configured webhooks.
- `http.rs`: shared `reqwest::Client` builder.
- `stockcharts.rs`: StockCharts fetch client, headers, retry attempts, and JSON decoding.
- `telemetry.rs`: tracing setup and optional Sentry initialization.

### Time Zone Handling

Critical: StockCharts uses Eastern Time (`America/New_York`). Alert timestamps must be parsed with Eastern timezone context to avoid missed or duplicated alerts, including DST transitions.

### HTTP Client Handling

The scheduler path must use one shared `reqwest::Client` clone. Do not create new clients inside polling loops; that was the source of a previous production memory leak in the Python implementation.

### Error Handling Strategy

- StockCharts fetches make three total attempts.
- Transient StockCharts failures return an empty list after logging.
- Discord webhook failures log and continue to the next webhook.
- The scheduler backs off for 5 minutes after 5 consecutive errors.
- Sentry initializes only when `SENTRY_DSN` is set.

## Development Commands

```bash
make all
cargo fmt --check
cargo clippy --all-targets --locked -- -D warnings
cargo test --locked
cargo build --locked
```

Run locally with:

```bash
DISCORD_WEBHOOK_URLS=https://discord.example/webhook cargo run --locked
```

## Testing

- Unit tests live inline in Rust modules.
- HTTP tests use `mockito`.
- Time tests use explicit Eastern Time timestamps.
- Config tests should verify URL splitting, trimming, deduplication, required plural webhooks, and interval bounds.
- Delivery tests should verify graceful degradation instead of crashes.

## Container Build

The Dockerfile is a Rust multi-stage build. The runtime image copies `/usr/local/bin/stockchartsalerts`, runs as a non-root `stockchartsalerts` user, and preserves build args `GIT_COMMIT` and `GIT_BRANCH` for Sentry release metadata.

## Environment Variables

Required:

- `DISCORD_WEBHOOK_URLS`: comma-separated Discord webhook URLs.

Optional:

- `MINUTES_BETWEEN_RUNS`: default `5`, range `1..=1440`.
- `SENTRY_DSN`: enables Sentry.
- `SENTRY_ENVIRONMENT`: default `production`.
- `GIT_COMMIT` and `GIT_BRANCH`: set at build time.

## Code Style

- Rust 1.96, edition 2024.
- Rustfmt formatting.
- Clippy with `-D warnings`.
- `thiserror` for typed errors.
- `tracing` for logs.
- Keep parsing/filtering/formatting logic pure and directly testable.
