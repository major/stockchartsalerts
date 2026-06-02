# StockCharts Alerts

StockCharts Alerts polls the [StockCharts predefined alerts](https://stockcharts.com/freecharts/alertsummary.html) feed and sends new market alerts to Discord webhooks. It is a Rust 1.96 service built on Tokio and one shared `reqwest::Client` so the scheduled loop reuses connections instead of creating clients per poll.

## Configuration

Required:

- `DISCORD_WEBHOOK_URLS`: comma-separated Discord webhook URLs. Duplicate URLs are ignored after trimming.

Optional:

- `MINUTES_BETWEEN_RUNS`: polling interval in minutes, from 1 to 1440. Defaults to 5.
- `SENTRY_DSN`: enables Sentry when set.
- `SENTRY_ENVIRONMENT`: defaults to `production`.
- `GIT_COMMIT` and `GIT_BRANCH`: injected by the container build and used for the Sentry release string.

The legacy singular `DISCORD_WEBHOOK_URL` variable is not supported.

## Development

This repository uses Rust 1.96 and edition 2024.

```bash
make all
```

`make all` runs formatting checks, clippy with warnings denied, tests, documentation checks, and a locked build. Run coverage checks with:

```bash
make coverage
make patch-coverage
```

`make coverage` enforces 90 percent line coverage with `cargo llvm-cov`. `make patch-coverage` checks changed-line coverage against `main` with `diff-cover`; use `DIFF_COVER='uvx diff-cover'` if `diff-cover` is not installed as a standalone command. Public docstring coverage is enforced by the crate-level `#![deny(missing_docs)]` lint, and `make doc` also denies broken rustdoc links.

Run locally with:

```bash
DISCORD_WEBHOOK_URLS=https://discord.example/webhook cargo run --locked
```

## Container

The GitHub Actions workflow builds `ghcr.io/major/stockchartsalerts:latest` with a Rust multi-stage Containerfile based on Red Hat hardened images. Build args `GIT_COMMIT` and `GIT_BRANCH` are preserved so Sentry releases are reported as `{git_branch}@{git_commit}`.
