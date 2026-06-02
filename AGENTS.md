# AGENTS.md

> Authoritative knowledge base for AI agents. Keep this file updated when substantial changes land.

## Project

StockCharts Alerts Bot: polls stockcharts.com predefined alerts, sends new ones to Discord webhooks, and runs as a scheduled loop in a container.

- Rust 1.96, edition 2024
- Entry point: `cargo run` in development, `/usr/local/bin/stockchartsalerts` in the container
- Container: `ghcr.io/major/stockchartsalerts:latest`, built from `Containerfile` with Red Hat hardened images

## Directory Layout

```text
src/
  main.rs         # thin Tokio entry point
  lib.rs          # module tree and top-level run function
  app.rs          # scheduler, polling loop, graceful shutdown, backoff
  alerts.rs       # alert model, filtering, Eastern Time parsing
  config.rs       # clap/env settings normalization and validation
  discord.rs      # Discord webhook formatting, payloads, and posting
  error.rs        # thiserror error enum and Result alias
  http.rs         # shared reqwest client builder and HTTP status handling
  stockcharts.rs  # StockCharts fetch client, headers, retry behavior, JSON decoding
  telemetry.rs    # tracing, optional Sentry initialization, and error capture
```

## Architecture

### Config (`config.rs`)

Configuration comes from CLI arguments and environment variables via `clap`.

- `DISCORD_WEBHOOK_URLS` is required and is the only supported webhook variable.
- `DISCORD_WEBHOOK_URL` is intentionally unsupported.
- Webhook URLs are split, trimmed, and deduplicated during settings normalization.
- `MINUTES_BETWEEN_RUNS` is bounded from 1 to 1440 and defaults to 5.
- Optional Sentry and release env vars: `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `GIT_COMMIT`, `GIT_BRANCH`.
- When `SENTRY_DSN` is configured, scheduler, application, and Discord webhook errors are captured in Sentry in addition to stdout logs. INFO logs still remain stdout-only.

### HTTP Client

`http.rs` builds one shared `reqwest::Client` with a 30 second timeout, 5 max idle connections per host, and 30 second idle pool timeout. It also centralizes HTTP success/status error mapping. `App::new` clones this shared client into both StockCharts and Discord clients; `reqwest::Client` clones share the same connection pool.

**Memory leak history**: Python versions created clients in loops and caused OOMKilled in production. Never create new HTTP clients inside the polling loop.

### Alert Flow

1. `StockChartsClient::get_alerts()` fetches JSON from stockcharts.com with three total attempts.
2. `new_alerts_since()` filters placeholders, malformed payloads, and alerts older than the previous run.
3. `DiscordClient::send_alert_to_webhooks()` posts formatted alerts to all configured webhooks.
4. Transient failures log and degrade gracefully instead of crashing the service.

### Scheduler (`app.rs`)

The scheduler runs one startup check immediately, then uses `tokio::time::interval` with `MissedTickBehavior::Delay` for recurring checks. After 5 consecutive errors, it backs off for 5 minutes; otherwise it waits 1 minute before retrying after an error. Ctrl-C triggers graceful shutdown.

## Critical Constraints

1. **Timezone**: StockCharts uses Eastern Time (`America/New_York`). ALL timestamp parsing MUST use ET context. Using UTC or naive timestamps will silently miss or duplicate alerts.
2. **HTTP client**: Never build `reqwest::Client` instances in polling loops. Use the shared client from `App::new`.
3. **Webhook config**: Only `DISCORD_WEBHOOK_URLS` is supported. Do not add singular `DISCORD_WEBHOOK_URL` compatibility.
4. **Error resilience**: StockCharts and Discord transient failures should log and continue where possible.

## Testing

Run `make all` for the full local check or `make test` for tests only.

### Patterns

- Unit tests live inline in `#[cfg(test)]` modules.
- HTTP mocking uses `mockito`.
- Time-sensitive tests pass explicit Eastern Time timestamps instead of relying on wall-clock time.
- Config tests should verify URL splitting, trimming, deduplication, required plural webhooks, and interval bounds.
- Assertions verify graceful degradation, webhook deduplication, retry counts, and no crashes on transient failures.

### Development Commands

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

## CI/CD

GitHub Actions:

1. `.github/workflows/main.yml`: Linux Rust quality gates (`fmt`, `clippy`, `test`, `build`) on Rust 1.96.0, followed by the `container` job.
2. `.github/workflows/audit.yml`: RustSec audit on dependency file changes, manual dispatch, and a daily schedule.
3. `container`: builds `Containerfile`, pushes `ghcr.io/major/stockchartsalerts:latest` only on `main`, then checks out `major/homehosted` and updates `apps/stockchartsalerts/helm/helmrelease.yaml` with the new image digest.

All actions are SHA-pinned. This repository does not publish a crate; avoid release-plz, cargo-dist, crates.io publishing, and GitHub Release binary workflows. Secrets: `GITHUB_TOKEN`, `HOMEHOSTED_PAT`.

## Tooling

| Tool | Config | Command |
|------|--------|---------|
| rustfmt | `rust-toolchain.toml` | `cargo fmt --check` |
| clippy | `.cargo/config.toml`, `Cargo.toml` | `cargo clippy --all-targets --locked -- -D warnings` |
| cargo test | `Cargo.toml` | `cargo test --locked` |
| cargo build | `Cargo.toml` | `cargo build --locked` |
| pre-commit | `.pre-commit-config.yaml` | auto on commit |
| renovate | `renovate.json` | dependency updates |
| codecov | `codecov.yaml` | coverage target |

## Code Style

- Rust 1.96, edition 2024.
- `#![deny(missing_docs)]` at crate root.
- Typed errors with `thiserror` and `crate::error::Result`.
- Rustfmt formatting and clippy with warnings denied.
- `tracing` for logs.
- Small pure helpers for parsing, filtering, and formatting so tests stay fast.
