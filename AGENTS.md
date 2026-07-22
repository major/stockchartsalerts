# AGENTS.md

> Authoritative knowledge base for AI agents. Keep this file updated when substantial changes land.

## Project

StockCharts Alerts Bot: polls stockcharts.com predefined alerts, sends new ones to Discord webhooks, and runs as a scheduled loop in a container.

- Go 1.25+, toolchain 1.26.5
- Entry point: `go run ./cmd/stockchartsalerts` in development, compiled binary at `/usr/local/bin/stockchartsalerts` in the container
- Container: `ghcr.io/major/stockchartsalerts:latest`, built from `Containerfile` with Red Hat hardened Go images

## Directory Layout

```text
cmd/
  stockchartsalerts/
    main.go         # thin entry point, loads config, initializes logging, runs app
internal/
  config/
    settings.go     # environment variable parsing and validation
  xerrors/
    errors.go       # error types and constructors
  httpx/
    client.go       # shared HTTP client builder with 30s timeout
  alerts/
    alerts.go       # alert model, filtering, Eastern Time parsing, DST handling
  discord/
    discord.go      # Discord webhook formatting, payloads, and posting
  stockcharts/
    client.go       # StockCharts fetch client, headers, retry behavior, JSON decoding
  telemetry/
    logging.go      # structured logging via log/slog
  app/
    app.go          # scheduler, polling loop, graceful shutdown, backoff
```

## Architecture

### Config (`internal/config`)

Configuration comes from environment variables only (no CLI flags).

- `DISCORD_WEBHOOK_URLS` is required and is the only supported webhook variable (comma-separated, trimmed, deduplicated).
- `DISCORD_WEBHOOK_URL` (singular) is intentionally unsupported.
- `MINUTES_BETWEEN_RUNS` is bounded from 1 to 1440 and defaults to 5.
- `GIT_COMMIT` and `GIT_BRANCH` are optional, default to "unknown", used for version logging.
- `LOG_LEVEL` controls structured logging verbosity (defaults to "info").

### HTTP Client

`internal/httpx` builds one shared `*http.Client` with a 30 second timeout, 5 max idle connections per host, and 30 second idle pool timeout. It also centralizes HTTP success/status error mapping via `EnsureSuccessStatus`. `app.New` uses this shared client for both StockCharts and Discord requests.

**Memory leak history**: Python versions created clients in loops and caused OOMKilled in production. Never create new HTTP clients inside the polling loop.

### Alert Flow

1. `stockcharts.GetAlerts()` fetches JSON from stockcharts.com with three total attempts (2 retries with [2s, 4s] delays).
2. `alerts.FilterAlerts()` drops placeholder rows and malformed payloads.
3. `alerts.NewAlertsSince()` keeps only alerts newer than the previous run and the latest-fired alert(s) per symbol.
4. `discord.SendAlertToWebhooks()` posts formatted alerts to all configured webhooks.
5. Transient failures log and degrade gracefully instead of crashing the service.

### Scheduler (`internal/app`)

The scheduler runs one startup check immediately, then uses `time.Ticker` with a configurable interval for recurring checks. After 5 consecutive errors, it backs off for 5 minutes; otherwise it waits 1 minute before retrying after an error. Ctrl-C (SIGINT) or SIGTERM triggers graceful shutdown via context cancellation.

### Telemetry (`internal/telemetry`)

Structured logging via `log/slog` with JSON output. Log level is controlled by the `LOG_LEVEL` environment variable (defaults to "info").

**Sentry note**: Sentry error tracking was present in the original Rust implementation and was intentionally dropped during the Go migration. Errors are logged via `log/slog` only. This is a deliberate scope reduction, not an oversight.

## Critical Constraints

1. **Timezone**: StockCharts uses Eastern Time (`America/New_York`). ALL timestamp parsing MUST use ET context via `alerts.StockChartsTimeZone()`. Using UTC or naive timestamps will silently miss or duplicate alerts.
2. **HTTP client**: Never build new `*http.Client` instances in polling loops. Use the shared client from `app.New`.
3. **Webhook config**: Only `DISCORD_WEBHOOK_URLS` (plural) is supported. Do not add singular `DISCORD_WEBHOOK_URL` compatibility.
4. **Error resilience**: StockCharts and Discord transient failures should log and continue where possible, never crash the process.

## Testing

Run `make all` for the full local check, `make test` for tests only, or `make coverage` for 95%+ line coverage enforcement.

### Patterns

- Unit tests live in `_test.go` files alongside their packages, using table-driven test patterns.
- HTTP mocking uses `net/http/httptest` for StockCharts and Discord endpoints.
- Time-sensitive tests pass explicit Eastern Time timestamps instead of relying on wall-clock time.
- Config tests verify URL splitting, trimming, deduplication, required plural webhooks, and interval bounds.
- Assertions verify graceful degradation, webhook deduplication, retry counts, and no crashes on transient failures.
- Coverage target: 95%+ line coverage per package. `cmd/stockchartsalerts` is deliberately 0% (thin entrypoint convention); all logic lives in `internal/app` which is fully tested.
- Docstring target: 100% exported-symbol godoc coverage, enforced via `golangci-lint` with the `revive` linter's `exported` rule.

### Development Commands

```bash
make all
gofumpt -l .
golangci-lint run
go test ./...
go vet ./...
go build ./cmd/stockchartsalerts
go test ./... -coverprofile=coverage.out
go run golang.org/x/vuln/cmd/govulncheck@latest ./...
```

Run locally with:

```bash
DISCORD_WEBHOOK_URLS=https://discord.example/webhook go run ./cmd/stockchartsalerts
```

## CI/CD

GitHub Actions:

1. `.github/workflows/main.yml`: Linux Go quality gates (`fmt`, `lint`, `test`, `coverage`, `doc`, `build`) on Go 1.26, followed by the `container` job.
2. `.github/workflows/audit.yml`: `govulncheck` audit on go.mod/go.sum changes, manual dispatch, and a daily schedule.
3. `container`: builds `Containerfile`, pushes `ghcr.io/major/stockchartsalerts:latest` only on `main`, then checks out `major/homehosted` and updates `apps/stockchartsalerts/helm/helmrelease.yaml` with the new image digest.

All actions are SHA-pinned. This repository does not publish a module; avoid release-plz, GoReleaser, pkg.go.dev publishing, and GitHub Release binary workflows. Secrets: `GITHUB_TOKEN`, `HOMEHOSTED_PAT`.

## Tooling

| Tool | Config | Command |
|------|--------|---------|
| gofumpt | `.editorconfig` | `gofumpt -l .` |
| golangci-lint | `.golangci.yml` | `golangci-lint run` |
| go test | `go.mod` | `go test ./...` |
| go vet | `go.mod` | `go vet ./...` |
| go build | `go.mod` | `go build ./cmd/stockchartsalerts` |
| go test -cover | `Makefile` | `make coverage` |
| govulncheck | `go.mod` | `go run golang.org/x/vuln/cmd/govulncheck@latest ./...` |
| pre-commit | `.pre-commit-config.yaml` | auto on commit |
| renovate | `renovate.json` | dependency updates |
| codecov | `codecov.yaml` | coverage target |

## Code Style

- Go 1.25+, toolchain 1.26.5.
- `gofumpt` formatting (enforced via `make fmt` and pre-commit).
- `golangci-lint` with warnings/lint errors treated as failures.
- 100% exported-symbol godoc comments (enforced via `golangci-lint` + `revive` linter's `exported` rule).
- `log/slog` for structured logging.
- Small pure helper functions for parsing, filtering, and formatting so tests stay fast.
- No runtime module dependencies (stdlib only; build tools like `gofumpt` and `govulncheck` are invoked via `go run`, not imported).
