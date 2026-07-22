# internal/telemetry/

The package contains the application's logging bootstrap. Its implementation is
`logging.go`; it does not provide metrics, tracing, error reporting, or a
logger abstraction.

## Responsibility

`telemetry.InitLogging` configures the process-wide default `log/slog` logger.
It selects the minimum emitted level from `LOG_LEVEL` and installs a text
handler that writes to standard output.

## Logging design and configuration flow

- `parseLogLevel` trims whitespace and compares case-insensitively. `debug`,
  `warn`, and `error` map to their corresponding `slog` levels; `info`, an
  empty value, and unrecognized values use `slog.LevelInfo`.
- `InitLogging` reads `LOG_LEVEL` directly with `os.Getenv`, creates a
  `slog.NewTextHandler(os.Stdout, ...)` with the selected level, and installs
  `slog.New(handler)` via `slog.SetDefault`.
- The binary calls `telemetry.InitLogging()` before loading configuration or
  starting the application, so startup and runtime failures use the same
  logger. There is no telemetry-specific configuration object or runtime
  reconfiguration path.
- Logging is structured at call sites using `slog` key/value attributes, while
  the configured output format is plain text.

## Flow

1. `cmd/stockchartsalerts/main.go` initializes the default logger.
2. `config.Load` and application startup run after logging is available; main
   logs configuration or application errors and exits when appropriate.
3. The scheduler in `internal/app` logs initial and recurring check results,
   shutdown, and consecutive polling failures.
4. StockCharts and alert processing log retry attempts, malformed payloads,
   and timestamp parse failures. Discord delivery logs sends and per-webhook
   failures while continuing with other webhooks.
5. These packages call the process-wide `slog.Info`, `slog.Warn`, and
   `slog.Error` functions directly; telemetry supplies their shared default
   handler and level filtering.

## Integration

- **Entry point:** `main` owns initialization and imports this package only for
  `InitLogging`.
- **Application packages:** `app`, `alerts`, `stockcharts`, and `discord` use
  the standard library's default `slog` logger rather than depending on a
  telemetry logger instance.
- **Configuration boundary:** `LOG_LEVEL` is independent of
  `config.Settings`; the other environment variables are loaded by
  `internal/config` and do not alter telemetry.
- **Security/error handling:** StockCharts and Discord clients sanitize errors
  before logging so URLs, query parameters, and webhook secrets are not
  exposed by log records.
