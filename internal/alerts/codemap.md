# internal/alerts/

Alert-domain normalization and selection for StockCharts responses.

## Responsibility

- Defines the `Alert` model used by the polling and Discord layers.
- Normalizes decoded payload fields, removes non-sendable rows, and selects alerts
  that fired after the previous successful poll.
- Owns StockCharts timestamp parsing and the canonical `America/New_York`
  location. The package embeds `time/tzdata` so this works in minimal images.

## Patterns

- `Alert.UnmarshalJSON` uses pointer fields to distinguish missing/null values
  from present values. Every string is trimmed; `bearish` defaults to `"no"`,
  `symbol` to `"UNKNOWN"`, and other absent/empty strings to empty strings.
  Unknown JSON fields are ignored.
- `FilterAlerts` is tolerant at the payload boundary: malformed JSON is logged
  and skipped, and the exact `NoAlertsPlaceholder` text is dropped. It returns
  valid alerts without failing the whole poll.
- `NewAlertsSince` composes `FilterAlerts` with timestamp parsing and a strict
  `firedAt.After(previousRun)` window. It then retains only the latest timestamp
  for each symbol; equal-time alerts are all retained. Input order is preserved
  among retained rows; the function does not sort them.
- The timezone is loaded once during package initialization and exposed through
  `StockChartsTimeZone`. Initialization panics if the embedded timezone cannot be
  loaded, rather than allowing silent timestamp errors.

## Flow

1. `stockcharts.Client` fetches the endpoint and returns raw JSON rows as
   `[]json.RawMessage`.
2. `app.SendAlertsOnceAt` converts `now` and its previous-run anchor to the
   StockCharts timezone, then passes the raw rows and anchor to
   `NewAlertsSince`.
3. `FilterAlerts` unmarshals each row into `Alert`, applies defaults/trimming,
   and drops placeholders or malformed rows.
4. `NewAlertsSince` removes rows whose `lastfired` timestamp cannot be parsed or
   is not newer than the anchor. Parse failures use `xerrors.TimeParse`, are
   logged, and do not abort the poll.
5. `ParseStockChartsTime` trims input, removes a trailing case-sensitive ` ET`,
   and accepts StockCharts' lowercase/no-space and uppercase/space AM/PM forms.
   It parses in `America/New_York`, including DST rules; ambiguous fall-back
   times resolve to the earliest instant. Unsupported input returns an error.
6. The resulting `[]Alert` is sent by `app` one alert at a time to Discord.

## Integration

- **StockCharts:** supplies raw JSON and the `alert`, `bearish`, `lastfired`,
  and `symbol` fields consumed by `Alert`.
- **App scheduler:** owns polling windows and calls `NewAlertsSince`; it updates
  its last-successful-run anchor only after the fetch/filter/send operation.
- **Discord:** consumes `alerts.Alert` for username/content and bearish
  formatting; this package does not perform delivery.
- **`internal/xerrors`:** provides the typed `KindTimeParse` error returned for
  unsupported StockCharts timestamps.
