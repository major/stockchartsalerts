package discord

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/major/stockchartsalerts/internal/alerts"
)

func TestPayloadFormat(t *testing.T) {
	tests := []struct {
		name     string
		alert    alerts.Alert
		expected Payload
	}{
		{
			name: "bullish_alert",
			alert: alerts.Alert{
				Alert:     "Test alert",
				Bearish:   "no",
				LastFired: "31 Jul 2024, 12:33pm",
				Symbol:    "$COMPQ",
			},
			expected: Payload{
				Username:  "$COMPQ",
				AvatarURL: AvatarURL,
				Content:   "💚  Test alert",
			},
		},
		{
			name: "bearish_alert",
			alert: alerts.Alert{
				Alert:     "Test alert",
				Bearish:   "yes",
				LastFired: "31 Jul 2024, 12:33pm",
				Symbol:    "$COMPQ",
			},
			expected: Payload{
				Username:  "$COMPQ",
				AvatarURL: AvatarURL,
				Content:   "🔴  Test alert",
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			payload := NewPayload(tt.alert)
			if payload.Username != tt.expected.Username {
				t.Errorf("username: got %q, want %q", payload.Username, tt.expected.Username)
			}
			if payload.AvatarURL != tt.expected.AvatarURL {
				t.Errorf("avatar_url: got %q, want %q", payload.AvatarURL, tt.expected.AvatarURL)
			}
			if payload.Content != tt.expected.Content {
				t.Errorf("content: got %q, want %q", payload.Content, tt.expected.Content)
			}
		})
	}
}

func TestPayloadDowRewrite(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "dow_crosses_above",
			input:    "Dow crosses above 41000",
			expected: "THE DOW, THE DOW IS ABOVE 41000",
		},
		{
			name:     "dow_crosses_above_with_decimals",
			input:    "Dow crosses above 41000.50",
			expected: "THE DOW, THE DOW IS ABOVE 41000.50",
		},
		{
			name:     "nasdaq_crosses_below",
			input:    "Nasdaq crosses below 17200",
			expected: "Nasdaq crosses below 17200",
		},
		{
			name:     "other_alert",
			input:    "S&P 500 Bullish Percent Index crosses above 70",
			expected: "S&P 500 Bullish Percent Index crosses above 70",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := formatAlertText(tt.input)
			if result != tt.expected {
				t.Errorf("got %q, want %q", result, tt.expected)
			}
		})
	}
}

func TestEmojiSelection(t *testing.T) {
	tests := []struct {
		name     string
		bearish  string
		expected string
	}{
		{
			name:     "bearish_yes",
			bearish:  "yes",
			expected: "🔴",
		},
		{
			name:     "bearish_no",
			bearish:  "no",
			expected: "💚",
		},
		{
			name:     "bearish_empty",
			bearish:  "",
			expected: "💚",
		},
		{
			name:     "bearish_other",
			bearish:  "maybe",
			expected: "💚",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			alert := alerts.Alert{Bearish: tt.bearish}
			result := emojiForAlert(alert)
			if result != tt.expected {
				t.Errorf("got %q, want %q", result, tt.expected)
			}
		})
	}
}

func TestSendAlertToMultipleWebhooks(t *testing.T) {
	// Create a test server that records requests.
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify the request is a POST with JSON content.
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if ct := r.Header.Get("Content-Type"); ct != "application/json" {
			t.Errorf("expected Content-Type: application/json, got %s", ct)
		}

		// Verify the payload format.
		var payload Payload
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Errorf("failed to decode payload: %v", err)
		}
		if payload.Username != "$COMPQ" {
			t.Errorf("expected username $COMPQ, got %s", payload.Username)
		}
		if payload.AvatarURL != AvatarURL {
			t.Errorf("expected avatar_url %s, got %s", AvatarURL, payload.AvatarURL)
		}
		if payload.Content != "💚  Test alert" {
			t.Errorf("expected content '💚  Test alert', got %s", payload.Content)
		}

		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	client := NewClient(&http.Client{})
	alert := alerts.Alert{
		Alert:     "Test alert",
		Bearish:   "no",
		LastFired: "31 Jul 2024, 12:33pm",
		Symbol:    "$COMPQ",
	}

	webhookURLs := []string{
		server.URL + "/webhooks/1/abc",
		server.URL + "/webhooks/2/def",
	}

	client.SendAlertToWebhooks(context.Background(), alert, webhookURLs)
}

func TestOneWebhookFailureDoesNotStopOthers(t *testing.T) {
	callCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		callCount++
		if callCount == 1 {
			// First webhook returns error.
			w.WriteHeader(http.StatusBadRequest)
		} else {
			// Second webhook succeeds.
			w.WriteHeader(http.StatusNoContent)
		}
	}))
	defer server.Close()

	client := NewClient(&http.Client{})
	alert := alerts.Alert{
		Alert:     "Test alert",
		Bearish:   "no",
		LastFired: "31 Jul 2024, 12:33pm",
		Symbol:    "$COMPQ",
	}

	webhookURLs := []string{
		server.URL + "/webhooks/1/abc",
		server.URL + "/webhooks/2/def",
	}

	client.SendAlertToWebhooks(context.Background(), alert, webhookURLs)

	if callCount != 2 {
		t.Errorf("expected 2 webhook calls, got %d", callCount)
	}
}

func TestWebhookURLNotExposedInError(t *testing.T) {
	client := NewClient(&http.Client{})
	alert := alerts.Alert{
		Alert:     "Test alert",
		Bearish:   "no",
		LastFired: "31 Jul 2024, 12:33pm",
		Symbol:    "$COMPQ",
	}

	// Use an unreachable local address with a secret token in the URL.
	webhookURL := "http://127.0.0.1:9/webhooks/secret-token"
	payload := NewPayload(alert)

	err := client.sendPayload(context.Background(), webhookURL, payload)
	if err == nil {
		t.Fatal("expected error, got nil")
	}

	errStr := err.Error()
	if strings.Contains(errStr, "secret-token") {
		t.Errorf("error message exposed webhook token: %s", errStr)
	}
	if strings.Contains(errStr, "127.0.0.1") {
		t.Errorf("error message exposed IP address: %s", errStr)
	}
	if strings.Contains(errStr, "9/webhooks") {
		t.Errorf("error message exposed webhook path: %s", errStr)
	}
}

func TestPayloadJSONSerialization(t *testing.T) {
	payload := Payload{
		Username:  "$COMPQ",
		AvatarURL: AvatarURL,
		Content:   "💚  Test alert",
	}

	data, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("failed to marshal payload: %v", err)
	}

	// Verify the JSON structure.
	var decoded map[string]interface{}
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("failed to unmarshal payload: %v", err)
	}

	if decoded["username"] != "$COMPQ" {
		t.Errorf("expected username $COMPQ, got %v", decoded["username"])
	}
	if decoded["avatar_url"] != AvatarURL {
		t.Errorf("expected avatar_url %s, got %v", AvatarURL, decoded["avatar_url"])
	}
	if decoded["content"] != "💚  Test alert" {
		t.Errorf("expected content '💚  Test alert', got %v", decoded["content"])
	}
}

func TestNewPayloadFromAlert(t *testing.T) {
	alert := alerts.Alert{
		Alert:     "Dow crosses above 41000",
		Bearish:   "no",
		LastFired: "31 Jul 2024, 12:33pm",
		Symbol:    "$INDU",
	}

	payload := NewPayload(alert)

	if payload.Username != "$INDU" {
		t.Errorf("expected username $INDU, got %s", payload.Username)
	}
	if payload.AvatarURL != AvatarURL {
		t.Errorf("expected avatar_url %s, got %s", AvatarURL, payload.AvatarURL)
	}
	if payload.Content != "💚  THE DOW, THE DOW IS ABOVE 41000" {
		t.Errorf("expected content '💚  THE DOW, THE DOW IS ABOVE 41000', got %s", payload.Content)
	}
}

func TestSendPayloadWithHTTPError(t *testing.T) {
	// Create a server that closes the connection immediately.
	server := httptest.NewServer(http.HandlerFunc(func(_ http.ResponseWriter, _ *http.Request) {
		// Simulate a connection error by not responding.
		panic("intentional panic to close connection")
	}))
	defer server.Close()

	client := NewClient(&http.Client{})
	payload := &Payload{
		Username:  "$COMPQ",
		AvatarURL: AvatarURL,
		Content:   "💚  Test alert",
	}

	// This should fail with a network error, but the error message should not expose the URL.
	err := client.sendPayload(context.Background(), server.URL, payload)
	if err == nil {
		t.Fatal("expected error, got nil")
	}

	errStr := err.Error()
	if strings.Contains(errStr, server.URL) {
		t.Errorf("error message exposed server URL: %s", errStr)
	}
}

func TestSendPayloadWithHTTPStatusError(t *testing.T) {
	// Create a server that returns a 500 error.
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	client := NewClient(&http.Client{})
	payload := &Payload{
		Username:  "$COMPQ",
		AvatarURL: AvatarURL,
		Content:   "💚  Test alert",
	}

	err := client.sendPayload(context.Background(), server.URL, payload)
	if err == nil {
		t.Fatal("expected error, got nil")
	}

	// Verify the error is about Discord status, not the URL.
	errStr := err.Error()
	if !strings.Contains(errStr, "Discord") {
		t.Errorf("expected Discord error, got: %s", errStr)
	}
}

func TestSendPayloadWithMarshalError(t *testing.T) {
	// Create a payload that can't be marshaled (this is hard to do with the current Payload struct).
	// Instead, test the context cancellation path.
	client := NewClient(&http.Client{})
	payload := &Payload{
		Username:  "$COMPQ",
		AvatarURL: AvatarURL,
		Content:   "💚  Test alert",
	}

	// Create a cancelled context.
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	err := client.sendPayload(ctx, "http://example.com", payload)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestSendAlertToWebhooksWithEmptyList(_ *testing.T) {
	// Test that sending to an empty webhook list doesn't crash.
	client := NewClient(&http.Client{})
	alert := alerts.Alert{
		Alert:     "Test alert",
		Bearish:   "no",
		LastFired: "31 Jul 2024, 12:33pm",
		Symbol:    "$COMPQ",
	}

	// This should not panic or error.
	client.SendAlertToWebhooks(context.Background(), alert, []string{})
}

func TestFormatAlertTextEdgeCases(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "dow_prefix_only",
			input:    "Dow crosses above ",
			expected: "THE DOW, THE DOW IS ABOVE ",
		},
		{
			name:     "dow_with_special_chars",
			input:    "Dow crosses above $SPX 100%",
			expected: "THE DOW, THE DOW IS ABOVE $SPX 100%",
		},
		{
			name:     "case_sensitive_dow",
			input:    "dow crosses above 41000",
			expected: "dow crosses above 41000",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := formatAlertText(tt.input)
			if result != tt.expected {
				t.Errorf("got %q, want %q", result, tt.expected)
			}
		})
	}
}

func TestSendPayloadWithInvalidURL(t *testing.T) {
	// Test that an invalid URL returns an error.
	client := NewClient(&http.Client{})
	payload := &Payload{
		Username:  "$COMPQ",
		AvatarURL: AvatarURL,
		Content:   "💚  Test alert",
	}

	// Use an invalid URL that will fail during request creation.
	err := client.sendPayload(context.Background(), "ht!tp://invalid", payload)
	if err == nil {
		t.Fatal("expected error, got nil")
	}

	// Verify the error message doesn't expose the invalid URL.
	errStr := err.Error()
	if strings.Contains(errStr, "ht!tp") {
		t.Errorf("error message exposed invalid URL: %s", errStr)
	}
}

func TestSendPayloadWithSuccessfulResponse(t *testing.T) {
	// Test that a successful response (204 No Content) returns no error.
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	client := NewClient(&http.Client{})
	payload := &Payload{
		Username:  "$COMPQ",
		AvatarURL: AvatarURL,
		Content:   "💚  Test alert",
	}

	err := client.sendPayload(context.Background(), server.URL, payload)
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
}

func TestSendPayloadWithOKResponse(t *testing.T) {
	// Test that a 200 OK response returns no error.
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client := NewClient(&http.Client{})
	payload := &Payload{
		Username:  "$COMPQ",
		AvatarURL: AvatarURL,
		Content:   "💚  Test alert",
	}

	err := client.sendPayload(context.Background(), server.URL, payload)
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
}

func TestSendPayloadWithContextCancellation(t *testing.T) {
	// Test that a cancelled context returns an error.
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client := NewClient(&http.Client{})
	payload := &Payload{
		Username:  "$COMPQ",
		AvatarURL: AvatarURL,
		Content:   "💚  Test alert",
	}

	// Create a cancelled context.
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	err := client.sendPayload(ctx, server.URL, payload)
	if err == nil {
		t.Fatal("expected error, got nil")
	}

	// Verify the error message doesn't expose the server URL.
	errStr := err.Error()
	if strings.Contains(errStr, server.URL) {
		t.Errorf("error message exposed server URL: %s", errStr)
	}
}
