# internal/

## Responsibility

`internal/` contains the application logic for polling StockCharts alerts,
selecting alerts that are new since the previous successful poll, and posting
them to configured Discord webhooks. The `cmd/stockchartsalerts` package is a
thin composition and process-lifecycle entry point; the scheduler and all
domain/integration behavior live here.

## Package boundaries

- **`app`** — Owns composition, polling orchestration, in-memory last-successful-run state, retry backoff, ticker scheduling, and shutdown behavior. `App.New` creates one shared HTTP client and gives it to both integration clients.
- **`config`** — Loads environment configuration into `Settings`: webhook URLs, polling interval, and build metadata. It trims and deduplicates webhook URLs and validates the interval.
- **`alerts`** — Defines `Alert`, JSON defaults/normalization, placeholder and malformed-row filtering, per-symbol latest-alert selection, and StockCharts timestamp parsing in `America/New_York` (including embedded tzdata).
- **`stockcharts`** — Fetches the StockCharts JSON endpoint with request headers, status checking, response decoding, and the default two-retry policy. It returns raw JSON rows so `alerts` owns domain filtering.
- **`discord`** — Converts an `alerts.Alert` into a webhook `Payload` and POSTs it to every configured webhook. Individual failures are sanitized, logged, and do not abort delivery to other webhooks.
- **`httpx`** — Provides the shared production `http.Client` (timeouts, connection pooling, redirect limit) and common 2xx status validation.
- **`telemetry`** — Initializes the process-wide `slog` logger and maps `LOG_LEVEL` to its level.
- **`xerrors`** — Defines categorized application errors and constructors for configuration, HTTP, StockCharts, payload, and timestamp failures.

Packages are narrowly scoped and communicate through concrete exported types
and functions; `app` is the only package that coordinates the domain and
external-service packages.

## Flow

1. `main` calls `telemetry.InitLogging`, then `config.Load`, constructs
   `app.New(settings)`, and creates a context cancelled by SIGINT/SIGTERM.
2. `App.RunUntilShutdown` performs one immediate `SendAlertsOnce` and then
   polls using a ticker. Successful checks restore the configured interval;
   failures use a 60-second retry delay, increasing to 300 seconds after five
   consecutive errors. Cancellation exits the loop.
3. `SendAlertsOnceAt` converts the clock to StockCharts Eastern Time and uses
   the last successful poll as the next window anchor (or the configured
   interval on the first run). `stockcharts.Client.GetAlerts` fetches raw
   rows.
4. `alerts.NewAlertsSince` calls `FilterAlerts`, parses each `LastFired`
   timestamp, discards rows at or before the window, and retains only the
   latest timestamp per symbol (including ties).
5. Each selected alert is passed to
   `discord.Client.SendAlertToWebhooks`, which formats and attempts delivery
   to all configured URLs. A successful StockCharts check advances the
   in-memory anchor even when an individual Discord webhook attempt fails.

## Integration

- **Configuration:** environment variables `DISCORD_WEBHOOK_URLS`,
  `MINUTES_BETWEEN_RUNS`, `GIT_COMMIT`, `GIT_BRANCH`, and `LOG_LEVEL`.
- **StockCharts:** HTTP GET to `stockcharts.DefaultAlertsURL`; requests use
  StockCharts-specific `Referer` and `User-Agent` headers and retry after
  2 seconds and 4 seconds. HTTP/client errors are sanitized where URLs could
  leak into logs.
- **Discord:** HTTP POST with JSON payloads to each configured webhook;
  non-2xx and network failures are logged without stopping the scheduler.
- **Process/runtime:** `context.Context`, `time.Ticker`, OS signal
  notification, `net/http`, and `log/slog` provide lifecycle, scheduling,
  transport, and logging primitives. No persistent storage is used; polling
  progress is held only in `App.lastSuccessfulRun`.
