# cmd/

The `cmd/` tree contains the executable entry point for the StockCharts Alerts Bot.

## Responsibility

`cmd/stockchartsalerts/main.go` assembles and starts the application. It owns process-level startup, configuration failure handling, signal-driven shutdown, and exit status; business logic remains in `internal/`.

## Design

The entry point is intentionally thin and imperative:

1. Initialize structured logging.
2. Load environment-backed settings.
3. Construct the application scheduler from those settings.
4. Run it with a context cancelled by `SIGINT` or `SIGTERM`.

Startup and runtime errors are logged with `log/slog`; invalid configuration and non-cancellation runtime failures terminate with status 1. Normal completion or cancellation exits with status 0.

## Flow

`main` calls `telemetry.InitLogging`, then `config.Load`. On success, the resulting settings are passed by value to `app.New`. A `signal.NotifyContext` supplies cancellation to `RunUntilShutdown`, which controls the polling lifecycle until a shutdown signal or terminal error. The command exits after the scheduler returns.

## Integration

The binary depends on:

- `internal/telemetry` for process-wide structured logging.
- `internal/config` for validated environment configuration.
- `internal/app` for scheduling, polling, and graceful shutdown.
- Go's `context`, `os/signal`, and `syscall` packages for lifecycle control.

Downstream StockCharts, Discord, HTTP, and alert-processing integrations are reached through `internal/app`; the command package does not call them directly.
