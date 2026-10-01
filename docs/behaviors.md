# Behavior Contract

This document records externally observable behavior for the Python service.
The **Business behavior** section covers which alerts are selected and what is
sent to Discord. The **Operational behavior** section covers configuration,
networking, scheduling, and process lifecycle.

## Business behavior

### Input rows and normalization

- The StockCharts response is an array of alert rows. A non-object entry or a
  non-string value for a recognized string field is skipped as a malformed row.
  A malformed row does not invalidate other rows. Invalid JSON or a non-array
  response fails the StockCharts fetch.
- Recognized field names are `alert`, `bearish`, `lastfired`, and `symbol`,
  matched without regard to case. Unrecognized fields are ignored.
- String values are trimmed. An absent, `null`, empty, or whitespace-only value
  uses its field default: `alert` and `lastfired` become `""`, `bearish` becomes
  `"no"`, and `symbol` becomes `"UNKNOWN"`.
- A row is a placeholder only when its normalized `alert` value is exactly
  `There are no alerts today`. That row is discarded.

### Timestamp parsing

- Alert timestamps use the `America/New_York` timezone, including its daylight
  saving rules. Never parse them as UTC or as the host's local time.
- Leading and trailing whitespace is ignored. A trailing uppercase ` ET` is
  optional and is removed before parsing.
- The accepted timestamp forms are `31 Jul 2024, 2:31pm` (lowercase `am` or
  `pm`, with no space before it) and `1 Aug 2024, 8:11 AM` (uppercase `AM` or
  `PM`, with a space before it). Date and time components separated by spaces
  accept repeated spaces, and hour `0` is accepted. Meridiem casing and spacing
  must still match one of these forms; mixed-case meridiem is not accepted.
- During the fall daylight-saving overlap, choose the earliest corresponding
  instant. For example, `3 Nov 2024, 1:30am` means the first 1:30 a.m. in New
  York, with the EDT offset.
- An invalid or unrepresentable timestamp, including a timezone conversion that
  exceeds Python's `datetime` range, is skipped.
- When feed rows are rejected, the poll emits at most one warning with aggregate
  counts for malformed rows and invalid timestamps. The warning does not include
  raw row values, symbols, timestamps, or exception text. Placeholder rows and
  valid rows superseded by a newer alert do not increase these counts.
- A malformed row counts once even if several recognized fields are invalid.
  Invalid timestamps are counted only for normalized, non-placeholder rows.

### New alert selection

- An alert must be strictly newer than the poll's previous-run anchor. An alert
  exactly at the anchor is not new.
- After the strict time filter, retain only the newest timestamp or timestamps
  for each symbol. Multiple alerts tied at that newest timestamp are all kept.
- Symbol grouping is case-sensitive. For example, `ABC` and `abc` are separate
  symbols.
- Selected alerts retain their input order. Rows for a symbol with an older
  timestamp are removed even when they appeared first.

### Discord payload and delivery

- For each selected alert, post one JSON object to every configured webhook in
  configuration order. Requests are sequential, not concurrent.
- The payload has exactly these fields: `username` is the symbol, `avatar_url`
  is `https://emojiguide.org/images/emoji/1/8z8e40kucdd1.png`, and `content` is
  the alert text with its icon and formatting.
- `content` starts with `🔴` when `bearish` is exactly `yes`. For every other
  value it starts with `💚`. The icon is followed by exactly two spaces.
- If alert text starts with the exact, case-sensitive prefix
  `Dow crosses above `, replace that prefix with
  `THE DOW, THE DOW IS ABOVE `. Leave all other alert text unchanged.
- Any 2xx HTTP response is successful. A failure for one webhook is logged and
  does not prevent attempts to the remaining webhooks.
- Discord posts are not retried. Delivery is best effort, not guaranteed.

### Poll anchor and delivery consequences

- The time for a poll is captured before fetching StockCharts. On the first
  poll, the lookback anchor is that captured time minus
  `MINUTES_BETWEEN_RUNS`. Later polls use the last successful-fetch time as the
  anchor.
- If fetching fails, the anchor does not change. After a successful fetch and
  alert-selection pass, the anchor advances to the time captured before that
  fetch, even if one or more Discord posts fail.
- The anchor exists only in memory. There is no durable watermark or delivery
  guarantee. A restart uses the normal interval lookback again, so an alert
  already delivered within that window can be duplicated. Alerts older than
  that lookback can be missed after a restart or extended outage.

## Operational behavior

### Configuration

- `DISCORD_WEBHOOK_URLS` is required. It is a comma-separated list; each value
  is trimmed, empty values are dropped, and duplicate values are removed while
  keeping the first occurrence. The singular `DISCORD_WEBHOOK_URL` is not
  supported.
- `MINUTES_BETWEEN_RUNS` defaults to `5`, must be integer text without leading
  or trailing whitespace, and must be between `1` and `1440` inclusive.
- Startup logs include a plain-text banner with `GIT_BRANCH` and the full
  `GIT_COMMIT` value. Both are optional and default to `unknown`.
- `LOG_LEVEL` accepts `debug`, `info`, `warn`, or `error`; the default and the
  fallback for an unknown value are `info`.
- Logs are plain text, not JSON. Sentry is not configured.

### HTTP clients and fetches

- The application creates one shared asynchronous `httpx2` client at startup
  and uses it for both StockCharts and Discord. Its request timeout is 30
  seconds. Close it during application shutdown; do not create clients in the
  polling loop.
- StockCharts is fetched from
  `https://stockcharts.com/j-sum/sum?cmd=alert`.
- A failed StockCharts fetch has three total attempts: the initial attempt,
  followed by retries after 2 seconds and 4 seconds. Exhausting attempts fails
  that poll. Discord requests have no retry policy.

### Scheduler and shutdown

- Run one check immediately at startup. The recurring schedule starts after
  that check, whether it succeeds or fails. The startup failure is excluded from
  the recurring consecutive-failure count.
- After a successful recurring check, reset the failure count and wait the
  configured polling interval before the next check.
- After a recurring failure, wait 60 seconds while the consecutive failure
  count is below five. Starting with the fifth consecutive failure, wait 300
  seconds. A successful check resets the count.
- SIGINT and SIGTERM cancel the async polling work. Shutdown closes the shared
  HTTP client.
