// Package app provides the scheduler and orchestration logic for stockchartsalerts.
package app

import (
	"context"
	"log/slog"
	"time"

	"github.com/major/stockchartsalerts/internal/alerts"
	"github.com/major/stockchartsalerts/internal/config"
	"github.com/major/stockchartsalerts/internal/discord"
	"github.com/major/stockchartsalerts/internal/httpx"
	"github.com/major/stockchartsalerts/internal/stockcharts"
)

// App orchestrates alert fetching and delivery.
type App struct {
	settings          config.Settings
	stockchartsClient *stockcharts.Client
	discordClient     *discord.Client
	// tickerInterval is the interval for the polling ticker. Defaults to MinutesBetweenRuns.
	// This is exposed for testing purposes.
	tickerInterval time.Duration
	// lastSuccessfulRun tracks the timestamp of the last successful poll.
	// Used to anchor the previousRun window for the next check, ensuring alerts
	// fired during extended outages (beyond MinutesBetweenRuns) are not dropped.
	lastSuccessfulRun time.Time
}

// New creates a new App with a shared HTTP client built from production defaults.
func New(settings config.Settings) *App {
	httpClient := httpx.NewClient()
	return &App{
		settings:          settings,
		stockchartsClient: stockcharts.NewClient(httpClient),
		discordClient:     discord.NewClient(httpClient),
		tickerInterval:    time.Duration(settings.MinutesBetweenRuns) * time.Minute,
	}
}

// NewWithClients creates a new App with explicitly provided clients.
// This is primarily for testing. The caller retains ownership of the clients.
func NewWithClients(settings config.Settings, scClient *stockcharts.Client, dcClient *discord.Client) *App {
	return &App{
		settings:          settings,
		stockchartsClient: scClient,
		discordClient:     dcClient,
		tickerInterval:    time.Duration(settings.MinutesBetweenRuns) * time.Minute,
	}
}

// WithTickerInterval sets a custom ticker interval for testing.
// This overrides the default interval derived from MinutesBetweenRuns.
func (a *App) WithTickerInterval(interval time.Duration) *App {
	a.tickerInterval = interval
	return a
}

// SendAlertsOnce fetches alerts and sends them to Discord webhooks.
// It uses the current time (in America/New_York) to compute the previous run window,
// anchored to the last successful poll time to avoid dropping alerts during extended outages.
// Returns the number of alerts sent.
func (a *App) SendAlertsOnce(ctx context.Context) (int, error) {
	return a.SendAlertsOnceAt(ctx, time.Now(), a.lastSuccessfulRun)
}

// SendAlertsOnceAt fetches alerts and sends them to Discord webhooks using an explicit "now" time
// and previous run anchor. If previousRunAnchor is zero, it defaults to now - MinutesBetweenRuns.
// This is primarily for testing. It filters alerts newer than the computed previousRun window
// and sends each to all configured Discord webhooks.
// Returns the number of alerts sent.
func (a *App) SendAlertsOnceAt(ctx context.Context, now time.Time, previousRunAnchor time.Time) (int, error) {
	// Convert now to America/New_York timezone for consistency with StockCharts timestamps
	now = now.In(alerts.StockChartsTimeZone())

	// Compute the previous run window, anchored to the last successful run
	var previousRun time.Time
	if previousRunAnchor.IsZero() {
		// First run or no prior successful run: use now - MinutesBetweenRuns
		previousRun = now.Add(-time.Duration(a.settings.MinutesBetweenRuns) * time.Minute)
	} else {
		// Use the last successful run as the anchor
		previousRun = previousRunAnchor.In(alerts.StockChartsTimeZone())
	}

	// Fetch alerts from StockCharts
	rawAlerts, err := a.stockchartsClient.GetAlerts(ctx)
	if err != nil {
		return 0, err
	}

	// Filter to new alerts since the previous run
	newAlerts := alerts.NewAlertsSince(rawAlerts, previousRun)

	// Send each alert to all configured Discord webhooks
	count := 0
	for _, alert := range newAlerts {
		a.discordClient.SendAlertToWebhooks(ctx, alert, a.settings.DiscordWebhookURLs)
		count++
	}

	// Update the last successful run time to anchor the next check
	a.lastSuccessfulRun = now

	return count, nil
}

// errorBackoffDuration returns the backoff duration based on the number of consecutive errors.
// It returns 60 seconds for fewer than 5 consecutive errors, and 300 seconds for 5 or more.
func errorBackoffDuration(consecutiveErrors int) time.Duration {
	if consecutiveErrors >= 5 {
		return 300 * time.Second
	}
	return 60 * time.Second
}

// RunUntilShutdown runs the alert polling loop until the context is cancelled.
// It performs one check immediately, then uses a ticker to run checks at regular intervals.
// On success, the consecutive error counter resets and the ticker is reset to the normal interval.
// On error, the counter increments and the ticker is reset to a backoff duration:
// 60 seconds normally, 300 seconds after 5 consecutive errors.
// The loop exits cleanly when ctx is cancelled (checked with priority via select).
//
// Note on missed-tick behavior: Go's stdlib time.Ticker naturally drops missed
// ticks rather than queuing them up. If the polling loop takes longer than the
// interval or the system is under load, the ticker skips the missed tick and
// waits for the next scheduled one instead of bursting through backlogged
// ticks. This is the desired behavior for this application.
func (a *App) RunUntilShutdown(ctx context.Context) error {
	// Run one check immediately
	count, err := a.SendAlertsOnce(ctx)
	if err != nil {
		slog.Error("initial alert check failed", "error", err)
	} else {
		slog.Info("initial alert check completed", "alerts_sent", count)
	}

	// Set up the ticker for recurring checks
	ticker := time.NewTicker(a.tickerInterval)
	defer ticker.Stop()

	consecutiveErrors := 0

	for {
		select {
		case <-ctx.Done():
			// Context cancelled (SIGINT/SIGTERM); exit cleanly
			slog.Info("shutdown signal received, exiting")
			return ctx.Err()
		case <-ticker.C:
			// Perform the alert check
			// Use the last successful run as the anchor for the next check
			count, err := a.SendAlertsOnceAt(ctx, time.Now(), a.lastSuccessfulRun)
			if err != nil {
				consecutiveErrors++
				slog.Error("alert check failed",
					"error", err,
					"consecutive_errors", consecutiveErrors)

				// Determine backoff duration and reset ticker
				backoffDuration := errorBackoffDuration(consecutiveErrors)
				ticker.Reset(backoffDuration)
			} else {
				// Success: reset the error counter and ticker to normal interval
				consecutiveErrors = 0
				ticker.Reset(a.tickerInterval)
				slog.Info("alert check completed", "alerts_sent", count)
			}
		}
	}
}
