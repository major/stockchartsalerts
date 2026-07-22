// Package stockcharts provides a client for fetching alerts from StockCharts.
package stockcharts

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"time"

	"github.com/major/stockchartsalerts/internal/httpx"
	"github.com/major/stockchartsalerts/internal/xerrors"
)

// DefaultAlertsURL is the default StockCharts alerts endpoint.
const DefaultAlertsURL = "https://stockcharts.com/j-sum/sum?cmd=alert"

// Client fetches alerts from StockCharts.
type Client struct {
	httpClient  *http.Client
	alertsURL   string
	retryDelays []time.Duration
}

// NewClient creates a new StockCharts client.
// It takes a shared HTTP client (typically from internal/httpx.NewClient).
func NewClient(httpClient *http.Client) *Client {
	return &Client{
		httpClient:  httpClient,
		alertsURL:   DefaultAlertsURL,
		retryDelays: []time.Duration{2 * time.Second, 4 * time.Second},
	}
}

// WithAlertsURL sets a custom alerts URL (primarily for testing).
func (c *Client) WithAlertsURL(url string) *Client {
	c.alertsURL = url
	return c
}

// WithRetryDelays sets custom retry delays (primarily for testing).
func (c *Client) WithRetryDelays(delays []time.Duration) *Client {
	c.retryDelays = delays
	return c
}

// GetAlerts fetches alerts from StockCharts.
// It returns the alerts or an error if the fetch fails.
func (c *Client) GetAlerts(ctx context.Context) ([]json.RawMessage, error) {
	return c.FetchAlerts(ctx)
}

// FetchAlerts fetches alerts from StockCharts with retry logic.
// It returns the raw JSON array or an error after exhausting all retries.
func (c *Client) FetchAlerts(ctx context.Context) ([]json.RawMessage, error) {
	var lastErr error
	totalAttempts := len(c.retryDelays) + 1 // 1 initial + N retries

	for attempt := 0; attempt < totalAttempts; attempt++ {
		if attempt > 0 {
			slog.Warn("retrying StockCharts fetch", "attempt", attempt)
			select {
			case <-time.After(c.retryDelays[attempt-1]):
			case <-ctx.Done():
				return nil, ctx.Err()
			}
		}

		alerts, err := c.fetchOnce(ctx)
		if err == nil {
			return alerts, nil
		}
		lastErr = err
	}

	return nil, lastErr
}

// fetchOnce performs a single fetch attempt.
func (c *Client) fetchOnce(ctx context.Context) ([]json.RawMessage, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.alertsURL, nil)
	if err != nil {
		return nil, xerrors.HTTPClient(scrubURLFromError(err))
	}

	// Set custom headers
	req.Header.Set("Referer", "https://stockcharts.com/freecharts/alertsummary.html")
	req.Header.Set("User-Agent", "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, xerrors.HTTPClient(scrubURLFromError(err))
	}
	defer func() { _ = resp.Body.Close() }()

	// Check HTTP status
	if err := httpx.EnsureSuccessStatus("StockCharts", resp.StatusCode); err != nil {
		// Drain the body to allow connection reuse before returning the error
		_, _ = io.Copy(io.Discard, resp.Body)
		return nil, err
	}

	// Read and decode response body
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, xerrors.HTTPClient(scrubURLFromError(err))
	}

	var alerts []json.RawMessage
	if err := json.Unmarshal(body, &alerts); err != nil {
		return nil, xerrors.StockCharts("failed to decode JSON response")
	}

	return alerts, nil
}

// scrubURLFromError removes the URL from error messages to prevent leaking
// sensitive information like query parameters or hostnames.
// It returns a generic error message instead of the full error details.
// Context cancellation and deadline exceeded errors are returned unchanged
// to allow proper shutdown handling.
func scrubURLFromError(err error) error {
	if err == nil {
		return nil
	}
	// Let context cancellation/deadline errors pass through unchanged
	// so graceful shutdown can be detected properly
	if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
		return err
	}
	// Return a generic error message without the URL details
	// This prevents leaking the URL, query parameters, or hostnames in logs
	return genericHTTPError
}

// genericHTTPError is a generic error used to replace detailed HTTP errors
// that might contain sensitive URL information.
var genericHTTPError = xerrors.StockCharts("HTTP request failed")
