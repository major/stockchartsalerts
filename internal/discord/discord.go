// Package discord provides Discord webhook payload formatting and delivery.
package discord

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strings"

	"github.com/major/stockchartsalerts/internal/alerts"
	"github.com/major/stockchartsalerts/internal/httpx"
)

const (
	// AvatarURL is the avatar URL displayed for webhook messages.
	AvatarURL = "https://emojiguide.org/images/emoji/1/8z8e40kucdd1.png"
)

// Client sends Discord webhook messages.
type Client struct {
	httpClient *http.Client
}

// NewClient creates a Discord client using the provided HTTP client.
// The client must not be nil and is not copied; the caller retains ownership.
func NewClient(httpClient *http.Client) *Client {
	return &Client{httpClient: httpClient}
}

// SendAlertToWebhooks sends an alert to all configured Discord webhooks,
// logging and continuing on per-webhook failures.
func (c *Client) SendAlertToWebhooks(ctx context.Context, alert alerts.Alert, webhookURLs []string) {
	slog.Info("sending alert to Discord", "alert", alert.Alert, "lastfired", alert.LastFired)

	for i, webhookURL := range webhookURLs {
		payload := NewPayload(alert)
		if err := c.sendPayload(ctx, webhookURL, payload); err != nil {
			slog.Error("Discord webhook failed",
				"webhook", i+1,
				"total", len(webhookURLs),
				"symbol", alert.Symbol,
				"error", err)
		} else {
			slog.Info("alert sent to Discord",
				"webhook", i+1,
				"total", len(webhookURLs),
				"symbol", alert.Symbol)
		}
	}
}

// sendPayload posts a payload to a webhook URL, returning a sanitized error
// that does not expose the webhook URL or any secrets.
func (c *Client) sendPayload(ctx context.Context, webhookURL string, payload *Payload) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal Discord payload: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, webhookURL, bytes.NewReader(body))
	if err != nil {
		// Sanitize request creation errors to not expose the webhook URL.
		return fmt.Errorf("failed to create Discord request")
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		// Sanitize the error to not expose the webhook URL or secrets.
		return sanitizeHTTPError(err)
	}
	defer func() { _ = resp.Body.Close() }()

	// Discard response body to allow connection reuse.
	_, _ = io.ReadAll(resp.Body)

	// Check for HTTP status errors.
	if err := httpx.EnsureSuccessStatus("Discord", resp.StatusCode); err != nil {
		return err
	}

	return nil
}

// sanitizeHTTPError returns a sanitized error message that does not expose
// the webhook URL or any query parameters/secrets.
// The http.Client.Do method always returns *url.Error for network errors,
// so we only need to handle that case.
func sanitizeHTTPError(_ error) error {
	// Return a generic message without the URL or underlying error details
	// that might contain the URL.
	return fmt.Errorf("discord webhook request failed")
}

// Payload is the JSON payload sent to Discord webhooks.
type Payload struct {
	// Username is the username displayed for the webhook message.
	Username string `json:"username"`
	// AvatarURL is the avatar URL displayed for the webhook message.
	AvatarURL string `json:"avatar_url"`
	// Content is the message content.
	Content string `json:"content"`
}

// NewPayload creates a Discord payload from an alert.
func NewPayload(alert alerts.Alert) *Payload {
	return &Payload{
		Username:  alert.Symbol,
		AvatarURL: AvatarURL,
		Content:   fmt.Sprintf("%s  %s", emojiForAlert(alert), formatAlertText(alert.Alert)),
	}
}

// emojiForAlert returns the emoji for an alert based on its bearish flag.
func emojiForAlert(alert alerts.Alert) string {
	if alert.Bearish == "yes" {
		return "🔴"
	}
	return "💚"
}

// formatAlertText rewrites specific alert text patterns.
// If the alert starts with "Dow crosses above ", it is rewritten to
// "THE DOW, THE DOW IS ABOVE <remainder>".
func formatAlertText(text string) string {
	const dowPrefix = "Dow crosses above "
	if strings.HasPrefix(text, dowPrefix) {
		remainder := strings.TrimPrefix(text, dowPrefix)
		return fmt.Sprintf("THE DOW, THE DOW IS ABOVE %s", remainder)
	}
	return text
}
