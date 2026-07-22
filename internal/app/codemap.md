# internal/app/

The application orchestration layer for the StockCharts alert polling service.

## Responsibility

`App` coordinates fetching, filtering, and delivery of alerts, and owns the
long-running polling loop. It does not parse configuration, implement HTTP
requests, format Discord payloads, or manage process signals.

The package currently contains `app.go`. `New` builds the production clients
and scheduler interval; `NewWithClients` and `WithTickerInterval` provide
explicit dependencies and timing for tests. `SendAlertsOnce`/`SendAlertsOnceAt`
perform one poll and return the number of alert records handed to the Discord
client.

## Design

* A concrete orchestration object holds normalized `config.Settings`, one
  StockCharts client, one Discord client, and the ticker interval. Production
  construction creates one shared `*http.Client` through `httpx.NewClient`
  and passes it to both service clients; no HTTP clients are created per poll.
* Polls are context-aware through the clients' request methods. StockCharts
  fetch failures are returned to the scheduler. Discord delivery is deliberately
  best-effort: the Discord client logs per-webhook failures, while the app still
  treats the poll as successful and advances its successful-run anchor.
* Time comparisons are normalized to StockCharts' `America/New_York` location.
  The first poll uses `now - MinutesBetweenRuns`; later polls use
  `lastSuccessfulRun`, so an outage does not shrink the next lookback window and
  drop alerts.
* `lastSuccessfulRun` is mutable scheduler state. It is updated only after a
  successful StockCharts fetch and alert-processing pass, and is not advanced
  when fetching fails.

## Flow

`RunUntilShutdown` performs a poll immediately, then creates a `time.Ticker` for
the configured interval. Each tick calls `SendAlertsOnceAt` with the current
time and the last successful anchor:

1. Convert the supplied current time and anchor to Eastern Time and determine
   the previous-run boundary.
2. Call `stockcharts.Client.GetAlerts`, which fetches the raw JSON alert rows
   (including its own retry behavior).
3. Call `alerts.NewAlertsSince`. It drops placeholders and malformed or
   unparsable rows, keeps rows newer than the boundary, and retains only the
   latest fired alert(s) per symbol (ties are retained).
4. Pass each resulting alert to
   `discord.Client.SendAlertToWebhooks` with all configured webhook URLs. The
   returned count is the number of alert records processed, not the number of
   webhook HTTP requests that succeeded.
5. Record the Eastern-Time `now` as `lastSuccessfulRun`.

The recurring loop resets its consecutive StockCharts error count and ticker to
the normal interval after success. On an error it increments the counter and
resets the ticker to 60 seconds, or 300 seconds after five or more consecutive
errors. Context cancellation is checked in the loop's select and exits cleanly
with `ctx.Err()`; the ticker is stopped on return. The initial poll logs its
result but does not increment the recurring error counter when it fails.

## Integration

* `cmd/stockchartsalerts/main.go` initializes telemetry, loads
  `config.Settings`, constructs `app.New`, and supplies a context cancelled by
  SIGINT/SIGTERM to `RunUntilShutdown`.
* `config.Settings` supplies `MinutesBetweenRuns` and the normalized plural
  `DISCORD_WEBHOOK_URLS` values used by the scheduler and delivery step.
* `httpx.NewClient` supplies the shared 30-second-timeout HTTP client used by
  both `stockcharts.Client` and `discord.Client`.
* `stockcharts.Client` owns the StockCharts endpoint, headers, retries, status
  handling, and JSON decoding; `app` only consumes its raw alert rows.
* `alerts` owns the alert model, Eastern-Time parsing, placeholder/malformed
  row filtering, and new/latest-per-symbol selection.
* `discord.Client` owns payload creation, webhook POSTs, and logging of
  per-webhook failures; `app` supplies alerts and webhook destinations.
