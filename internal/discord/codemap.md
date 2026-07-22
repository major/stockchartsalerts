# internal/discord/

The package adapts a validated `alerts.Alert` into a Discord webhook request and
delivers it to each configured webhook.

## Responsibility

- Owns Discord message formatting and HTTP webhook delivery.
- Does not fetch or filter StockCharts alerts, parse timestamps, or own webhook
  configuration.
- Exposes `Client`, `NewClient`, `Payload`, `NewPayload`, and the exported
  `AvatarURL` constant.

## Patterns

- `Client` receives an existing `*http.Client`; it does not create clients per
  request. Production wiring supplies the shared client used by the rest of the
  application.
- `NewPayload` is a small pure mapping from `alerts.Alert` to JSON fields:
  `username` is the symbol, `avatar_url` is the fixed `AvatarURL`, and `content`
  is an emoji followed by two spaces and the alert text.
- A bearish value exactly equal to `"yes"` uses `🔴`; every other value uses
  `💚`. Alert text beginning exactly with `"Dow crosses above "` is rewritten to
  `"THE DOW, THE DOW IS ABOVE "` plus the remainder.

## Webhook payload and control flow

`SendAlertToWebhooks` logs the alert, then iterates over the supplied URLs in
  order. It creates a payload for each URL and calls the internal
  `sendPayload` helper. The helper marshals the payload, creates a context-bound
  `POST`, sets `Content-Type: application/json`, sends it through the injected
  client, drains and closes the response body, and accepts any 2xx status.

The method is intentionally best-effort: it logs success or a per-webhook
failure and continues to the remaining URLs. An empty URL list is a no-op.
It has no retry loop and returns no error, so the caller's alert count reflects
alerts processed by the application rather than confirmed successful webhook
posts.

## Error behavior

- JSON marshal failures and request-construction failures stop the individual
  send. Request-construction errors are replaced with a generic message.
- Transport, timeout, and context errors are sanitized to
  `discord webhook request failed`; webhook URLs, paths, query parameters, and
  secrets are not included in these errors.
- Non-2xx responses are converted through `httpx.EnsureSuccessStatus("Discord", …)`.
  The response body is still consumed before status validation so connections
  can be reused.
- `SendAlertToWebhooks` reports these failures through structured logging and
  does not abort delivery to later webhooks.

## Integration

- `internal/app` constructs the Discord client in `app.New` with the shared
  client from `internal/httpx`. During each successful StockCharts poll,
  `app.SendAlertsOnceAt` gets new `alerts.Alert` values from
  `alerts.NewAlertsSince` and passes each alert plus configured webhook URLs to
  `SendAlertToWebhooks`.
- `internal/alerts.Alert` is the input contract. Alert filtering and
  Eastern-Time timestamp handling occur before this package is called.
- `internal/httpx` supplies the common HTTP success-status mapping; request
  timeout, transport, connection reuse, and redirect behavior come from the
  injected `*http.Client`.
