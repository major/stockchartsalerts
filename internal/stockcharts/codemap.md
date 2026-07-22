# internal/stockcharts/

The package is the boundary between the application and StockCharts' alert
endpoint. It owns request construction, response transport, retry timing, and
decoding the endpoint response into raw JSON records. Alert interpretation and
filtering remain in `internal/alerts`.

## Responsibility

- `Client` fetches `https://stockcharts.com/j-sum/sum?cmd=alert` by default.
- `NewClient` receives an existing `*http.Client`; callers should share the
  production client rather than create one in the polling loop.
- `GetAlerts` is the public compatibility-facing method and delegates directly
  to `FetchAlerts`, which returns `[]json.RawMessage` so downstream code owns
  alert-schema validation and filtering.
- `WithAlertsURL` and `WithRetryDelays` mutate the client for endpoint and
  timing overrides, primarily in tests.

## Design

The client uses a small two-layer pattern: `FetchAlerts` handles attempts and
backoff, while `fetchOnce` performs exactly one HTTP request and decode. Every
request carries the caller's context plus the StockCharts alert-summary
`Referer` and a browser-like `User-Agent`.

The default policy is one initial attempt followed by two retries, delayed by
2 seconds and 4 seconds. The retry slice determines the total attempt count
(`len(retryDelays) + 1`); a successful attempt returns immediately.

## Flow

1. `app.New` builds one shared `httpx.NewClient` and injects it into
   `stockcharts.NewClient`; `App.SendAlertsOnceAt` calls `GetAlerts`.
2. `FetchAlerts` calls `fetchOnce`. Before each retry it logs a warning and
   waits with a context-aware `select`; cancellation during the wait returns
   `ctx.Err()` without another request.
3. `fetchOnce` creates a context-bound `GET` request and calls the injected
   HTTP client. It defers response-body closure.
4. Non-2xx responses are rejected through
   `httpx.EnsureSuccessStatus("StockCharts", status)`. The body is drained
   before returning so the connection can be reused.
5. A successful response is read in full and unmarshaled as a JSON array of
   `json.RawMessage`. The raw records are returned unchanged; no timestamps,
   symbols, placeholders, or alert windows are processed here.
6. After all attempts fail, `FetchAlerts` returns the last attempt's error.
   `app` propagates that error and does not deliver or count alerts for the
   failed fetch.

## Integration

- `internal/httpx` supplies the shared client (30-second client/dial timeout,
  connection pooling, and redirect limiting) and maps non-2xx status codes to
  typed HTTP-status errors.
- `internal/xerrors` classifies transport failures as `KindHTTPClient`, HTTP
  status failures as `KindHTTPStatus`, and invalid JSON as
  `KindStockCharts`. Transport error details that may contain URLs,
  hostnames, or query parameters are scrubbed; context cancellation and
  deadline errors are preserved as the wrapped cause.
- `internal/app` owns scheduling, logging, and error backoff. On a successful
  fetch it passes the raw array to `internal/alerts.NewAlertsSince`, then sends
  the resulting alerts through `internal/discord`.

`fetchOnce` also converts request-construction, request-execution, and body
read failures to `xerrors.HTTPClient` errors. Invalid JSON is not retried
specially: it follows the same retry loop as transport and status failures, then
the final error is returned. HTTP status errors likewise participate in the
retry loop.
