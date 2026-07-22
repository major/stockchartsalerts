# StockCharts Alerts

StockCharts Alerts polls the [StockCharts predefined alerts](https://stockcharts.com/freecharts/alertsummary.html) feed and sends new market alerts to Discord webhooks. It is a Go 1.25+ service built with one shared `*http.Client` so the scheduled loop reuses connections instead of creating clients per poll.

## Configuration

Required:

- `DISCORD_WEBHOOK_URLS`: comma-separated Discord webhook URLs. Duplicate URLs are ignored after trimming.

Optional:

- `MINUTES_BETWEEN_RUNS`: polling interval in minutes, from 1 to 1440. Defaults to 5.
- `LOG_LEVEL`: structured logging level (debug, info, warn, error). Defaults to info.
- `GIT_COMMIT` and `GIT_BRANCH`: injected by the container build and used for version logging.

The legacy singular `DISCORD_WEBHOOK_URL` variable is not supported.

## Development

This repository uses Go 1.25+ with toolchain 1.26.5.

```bash
make all
```

`make all` runs formatting checks, linting, tests, documentation checks, and a build. Run coverage checks with:

```bash
make coverage
```

`make coverage` enforces 95 percent line coverage with `go test -coverprofile`. Public docstring coverage is enforced by `golangci-lint` with the `revive` linter's `exported` rule, and `make lint` also checks for missing doc comments on exported symbols.

Run locally with:

```bash
DISCORD_WEBHOOK_URLS=https://discord.example/webhook go run ./cmd/stockchartsalerts
```

## Container

The GitHub Actions workflow builds `ghcr.io/major/stockchartsalerts:latest` with a Go multi-stage Containerfile based on Red Hat hardened images. Build args `GIT_COMMIT` and `GIT_BRANCH` are preserved so version information is available at runtime.
