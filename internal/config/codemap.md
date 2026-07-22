# internal/config/

Configuration boundary for the StockCharts Alerts Bot. The package converts
environment variables into one normalized, validated `Settings` value for the
application; it does not read files, parse command-line flags, or create
clients.

## Responsibility

`settings.go` defines:

- `Settings`, containing the polling interval, Discord webhook destinations,
  and optional build metadata (`GitCommit` and `GitBranch`).
- `Load`, the single entry point for reading and validating environment
  configuration.
- `Release`, which formats build metadata as `branch@commit`.

Configuration errors are created with `xerrors.Config`, so callers receive the
shared `xerrors.KindConfig` category and a human-readable message.

## Patterns and normalization

- Configuration is environment-only and is loaded on demand; `Load` returns a
  pointer to an immutable-by-convention `Settings` value plus an error.
- `MINUTES_BETWEEN_RUNS` defaults to `5` when unset, then is parsed with
  `strconv.Atoi` and checked against the inclusive range `1..1440`.
- `DISCORD_WEBHOOK_URLS` is a comma-separated list. `normalizeWebhookURLs`
  trims each entry, drops empty entries, and deduplicates while preserving the
  first-seen order. The package checks that at least one entry remains, but it
  does not validate URL syntax or contact Discord. Only this plural variable is
  read; a singular webhook variable is not a compatibility path.
- `GIT_COMMIT` and `GIT_BRANCH` are optional. Each is trimmed and falls back to
  `"unknown"` when unset, empty, or whitespace-only.
- The private normalization helpers are pure transformations, keeping
  environment access and validation centralized in `Load`.

## Environment and validation flow

1. `Load` reads `MINUTES_BETWEEN_RUNS`. A present but non-integer value fails;
   an unset value uses the five-minute default. Values outside `1..1440` fail.
2. It reads and normalizes `DISCORD_WEBHOOK_URLS`. An unset, empty, or
   all-whitespace/list-empty value fails because at least one webhook is
   required.
3. It normalizes the two optional build metadata variables, applying the
   `unknown` defaults.
4. On success, it returns a populated `Settings`; on the first validation
   failure, it returns `nil` and a configuration error.

There is no mutation or reloading mechanism after `Load`; downstream code
receives the resulting values explicitly.

## Integration

- `cmd/stockchartsalerts/main.go` initializes logging, calls `config.Load`,
  logs the error and exits with status 1 on failure, then passes the dereferenced
  settings to `app.New`.
- `internal/app` stores the settings by value. `MinutesBetweenRuns` determines
  the normal scheduler ticker interval, and `DiscordWebhookURLs` is passed to
  Discord delivery for every new alert. `GitCommit` and `GitBranch` are carried
  with the settings and can be rendered through `Release`; the current app
  orchestration does not otherwise consume them.
- `internal/config/settings_test.go` exercises the normalization helpers,
  defaults, release formatting, and the success and failure paths of `Load`.
