# StockCharts Alerts

StockCharts Alerts polls the [StockCharts predefined alerts](https://stockcharts.com/freecharts/alertsummary.html) feed and sends new market alerts to Discord webhooks. It requires Python 3.14 or newer and is managed with `uv`.

The package lives in `src/stockchartsalerts/`. Its `stockchartsalerts` console script starts the polling service. One shared asynchronous `httpx2` client is created at application startup and reused for StockCharts and Discord requests. It has a 30-second timeout and is closed during shutdown.

## Configuration

Required:

- `DISCORD_WEBHOOK_URLS`: comma-separated Discord webhook URLs. Values are trimmed, empty values are ignored, and duplicates are removed while preserving their first occurrence. At least one URL is required.

Optional:

- `MINUTES_BETWEEN_RUNS`: polling interval in minutes, from 1 to 1440. Defaults to 5. The value must be an integer without whitespace padding.
- `LOG_LEVEL`: text logging level (`debug`, `info`, `warn`, or `error`). Defaults to `info`.
- `GIT_COMMIT` and `GIT_BRANCH`: optional release labels in the startup log. Each defaults to `unknown`.

Only `DISCORD_WEBHOOK_URLS` is supported. The singular `DISCORD_WEBHOOK_URL` variable is not supported.

## Alert behavior

Timestamps are interpreted in `America/New_York`. A poll selects alerts newer than its in-memory lookback anchor and keeps the latest timestamp for each symbol. Delivery to webhooks is sequential and best effort. See [the behavior contract](docs/behaviors.md) for exact parsing, filtering, payload, retry, and delivery guarantees.

## Development

Install the project dependencies from the locked environment and run the console script:

```bash
uv sync --locked
uv run stockchartsalerts
```

Run the full local quality checks:

```bash
make all
```

`make all` runs the formatting check, lint, `mypy`, Pyright, randomized tests
with branch coverage, and `uv build`. The Makefile also provides `fmt`, `lint`,
`types`, `test`, `coverage`, and `build` targets for running those checks
separately. Tests are randomized by `pytest-randomly`; reproduce a run with its
reported seed by passing `--randomly-seed=<seed>` to `uv run --locked pytest`.
The dependency audit is separate:

```bash
make audit
```

`make audit` runs `pip-audit`. Container runtime and image details are maintained separately from this application setup guide.
