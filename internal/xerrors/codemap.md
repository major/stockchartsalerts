# internal/xerrors/

## Responsibility

`xerrors` is the application's shared error vocabulary. It classifies failures
without performing I/O, logging, retries, or recovery, so callers can preserve
context while the scheduler and other boundaries decide how to react.

## Error design and patterns

- `Error` is the concrete error type. It carries a `Kind`, an optional wrapped
  `Err`, a service and HTTP `StatusCode` for status failures, and a rendered
  `Message`.
- The six categories are `alert_payload`, `config`, `http_client`,
  `http_status`, `stockcharts`, and `time_parse`.
- Constructors return `error` values with stable, human-readable prefixes:
  `AlertPayload`, `Config`, `HTTPClient`, `HTTPStatus`, `StockCharts`, and
  `TimeParse`. `HTTPClient` retains its underlying error; the other
  constructors do not wrap one.
- `Error()` prefers `Message`, then `Err.Error()`, then the string form of
  `Kind`. `Unwrap()` exposes `Err` for standard `errors.Is`/`errors.As` chains.
- `Error.Is` matches another `*Error` by `Kind` only. The `Is<Type>` helpers
  use `errors.Is` with a kind-only sentinel, so they also work through wrapped
  errors. `EnsureSuccessStatus` treats every HTTP status from 200 through 299
  as success and returns an `HTTPStatus` error otherwise.

## Flow

The package has no internal stateful flow: a caller selects a constructor at an
error boundary, receives an `*Error`, and may classify it later with an
`Is<Type>` helper or inspect the wrapped cause with standard library error
functions. HTTP callers normally pass a service name and response status to
`EnsureSuccessStatus`; successful statuses return `nil`, while all other
statuses become `HTTPStatus` values.

## Integration

- `config.Load` returns `Config` for invalid or missing environment settings.
- `httpx.EnsureSuccessStatus` delegates status classification to this package;
  `stockcharts.Client` uses it for StockCharts responses and wraps request or
  body-read failures as `HTTPClient`. StockCharts JSON decode failures are
  classified as `StockCharts`, and its retry loop returns the final error.
- `alerts.ParseStockChartsTime` returns `TimeParse` for unsupported timestamp
  formats. `alerts.FilterAlerts` currently logs and skips malformed payloads;
  it does not create `AlertPayload` errors.
- `app` propagates fetch errors and logs them in its polling/backoff loop. The
  package itself does not send errors to Discord or perform telemetry.
