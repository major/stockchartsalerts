# internal/httpx/

## Responsibility

`httpx` centralizes the shared HTTP client configuration and common HTTP status
validation used by the StockCharts and Discord integrations. It does not own
request construction, response decoding, retries, or logging.

## Patterns

- `NewClient` returns one configured `*http.Client`: a 30-second total request
  timeout, a dial timeout of `HTTPTimeout`, five maximum idle connections per
  host, and a 30-second idle connection timeout.
- Redirects are capped at ten. Once ten prior redirects have been followed,
  the redirect policy returns `http.ErrUseLastResponse`, leaving the response
  at the limit for the caller to handle.
- Callers pass request contexts to `http.NewRequestWithContext`; `httpx` does
  not create clients inside the polling loop or wrap request execution.

## HTTP client and status errors

`HTTPTimeout` is the exported 30-second timeout constant. `EnsureSuccessStatus`
delegates to `xerrors.EnsureSuccessStatus`: every status from 200 through 299
is successful; any other status returns an `xerrors.KindHTTPStatus` error that
includes the service name and status code. Transport/request failures are
classified by the integration clients with `xerrors.KindHTTPClient`; this
package does not alter or sanitize those errors.

## Flow

`app.New` constructs one client with `httpx.NewClient` and injects that same
client into both `stockcharts.NewClient` and `discord.NewClient`. StockCharts
uses `EnsureSuccessStatus("StockCharts", ...)` after each fetch and drains
non-success bodies before returning. Discord uses
`EnsureSuccessStatus("Discord", ...)` after draining every response body.
StockCharts owns its three-attempt retry policy; Discord owns per-webhook
failure logging and continuation.
