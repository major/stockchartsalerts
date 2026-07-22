# cmd/stockchartsalerts/

The command package is the process entry point for the StockCharts Alerts Bot.

## Responsibility

`main.go` owns process-level startup and shutdown only. It initializes logging,
loads and validates environment configuration, constructs the application, and
keeps the process alive until a termination signal or fatal application error.
Alert fetching, filtering, delivery, scheduling, and retry behavior belong to
`internal/app` and its collaborators.

## Design

This is a deliberately thin composition root:

- `telemetry.InitLogging` installs the default `log/slog` logger and applies
  `LOG_LEVEL`.
- `config.Load` converts environment variables into normalized `config.Settings`
  and rejects invalid or incomplete configuration.
- `app.New` wires the settings into the scheduler and its StockCharts and
  Discord clients (including the shared HTTP client).
- `signal.NotifyContext` provides cancellation-based lifecycle control for
  SIGINT and SIGTERM.

The command has no flags, persistent state, or domain logic of its own.

## Flow

1. Initialize text logging to stdout.
2. Load configuration. A configuration error is logged and terminates the
   process with exit status 1.
3. Construct an `app.App` from the validated settings.
4. Create a context cancelled by SIGINT or SIGTERM, then call
   `RunUntilShutdown`.
5. The application performs its initial alert check, then runs its polling loop
   with normal intervals and error backoff. The command waits synchronously.
6. Context cancellation is treated as a clean shutdown. Any other returned
   error is logged and exits with status 1; successful shutdown exits with
   status 0.

## Integration

- **Configuration:** reads `DISCORD_WEBHOOK_URLS`, `MINUTES_BETWEEN_RUNS`,
  optional `GIT_COMMIT`/`GIT_BRANCH`, and logging reads `LOG_LEVEL`.
- **Telemetry:** uses `internal/telemetry` for logger setup and `log/slog` for
  startup and application errors.
- **Application orchestration:** delegates scheduling and alert processing to
  `internal/app.App`.
- **Operating system:** consumes SIGINT/SIGTERM and reports failure through
  process exit status; no HTTP or Discord calls are made directly here.
