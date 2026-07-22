# Repository Atlas: StockCharts Alerts Bot

## Project Responsibility

This Go service polls StockCharts' predefined-alert endpoint, identifies alerts
newer than the last successful check in Eastern Time, and posts each result to
configured Discord webhooks. It runs as a long-lived, signal-aware container
process with bounded retry and backoff behavior.

## System Entry Points

- `cmd/stockchartsalerts/main.go`: Composition root; initializes logging, loads
  environment configuration, starts `app.App`, and handles SIGINT/SIGTERM.
- `internal/app/app.go`: Scheduler and polling orchestration; wires one shared
  HTTP client into the StockCharts and Discord integrations.
- `go.mod`: Go 1.26 module and toolchain definition.
- `Makefile`: Formatting, linting, test, build, coverage, and vulnerability
  audit commands.
- `Containerfile`: Production container build for the service binary.
- `.github/workflows/`: Quality, container publishing, deployment-update, and
  scheduled vulnerability-audit automation.

## Primary Alert Flow

1. The command initializes `log/slog`, loads validated environment settings,
   constructs `app.App`, and waits for a termination signal.
2. `app` immediately fetches StockCharts alerts, then repeats at the configured
   interval with short retry delays after failures and a longer delay after five
   consecutive failures.
3. `stockcharts` performs the GET request and retry policy; `alerts` parses and
   filters raw rows using the `America/New_York` timestamp context.
4. `alerts` retains only rows newer than the previous successful poll and the
   most recent fired alert(s) for each symbol.
5. `discord` formats every selected alert and best-effort posts it to all
   configured webhooks. The successful-poll anchor is advanced after a
   successful fetch and processing pass.

## Repository Directory Map

| Directory | Responsibility summary | Detailed map |
| --- | --- | --- |
| `cmd/` | Contains the executable command tree and keeps process concerns separate from application logic. | [cmd/codemap.md](cmd/codemap.md) |
| `cmd/stockchartsalerts/` | Thin composition root for logging, configuration, lifecycle signals, and application startup. | [cmd/stockchartsalerts/codemap.md](cmd/stockchartsalerts/codemap.md) |
| `internal/` | Private application layer containing orchestration, domain logic, integrations, and shared infrastructure. | [internal/codemap.md](internal/codemap.md) |
| `internal/app/` | Coordinates polling, alert selection, delivery, in-memory progress, backoff, and graceful shutdown. | [internal/app/codemap.md](internal/app/codemap.md) |
| `internal/config/` | Converts environment variables into normalized, validated application settings. | [internal/config/codemap.md](internal/config/codemap.md) |
| `internal/alerts/` | Normalizes StockCharts rows, parses Eastern Time timestamps, and selects new latest-per-symbol alerts. | [internal/alerts/codemap.md](internal/alerts/codemap.md) |
| `internal/discord/` | Formats alerts into Discord webhook payloads and performs best-effort delivery. | [internal/discord/codemap.md](internal/discord/codemap.md) |
| `internal/stockcharts/` | Fetches and decodes StockCharts alerts with headers, status handling, and retry delays. | [internal/stockcharts/codemap.md](internal/stockcharts/codemap.md) |
| `internal/httpx/` | Builds the shared HTTP client and centralizes 2xx status validation. | [internal/httpx/codemap.md](internal/httpx/codemap.md) |
| `internal/xerrors/` | Defines typed error categories and constructors shared across application boundaries. | [internal/xerrors/codemap.md](internal/xerrors/codemap.md) |
| `internal/telemetry/` | Configures the process-wide structured logging handler and level. | [internal/telemetry/codemap.md](internal/telemetry/codemap.md) |

## Operational Constraints

- All StockCharts timestamps must be handled in `America/New_York`.
- `DISCORD_WEBHOOK_URLS` is the only supported webhook configuration variable.
- The polling loop reuses the HTTP client created in `app.New`; it must not
  allocate clients per poll.
- StockCharts and Discord failures are logged and handled without crashing the
  process where possible.
