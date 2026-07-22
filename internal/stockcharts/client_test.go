package stockcharts

import (
	"bytes"
	"compress/gzip"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/major/stockchartsalerts/internal/xerrors"
)

func TestGetAlertsSuccessful(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify headers
		if r.Header.Get("Referer") != "https://stockcharts.com/freecharts/alertsummary.html" {
			t.Errorf("unexpected Referer header: %s", r.Header.Get("Referer"))
		}
		if r.Header.Get("User-Agent") != "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0" {
			t.Errorf("unexpected User-Agent header: %s", r.Header.Get("User-Agent"))
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode([]map[string]string{
			{"alert": "test alert 1"},
			{"alert": "test alert 2"},
		})
	}))
	defer server.Close()

	client := NewClient(http.DefaultClient).WithAlertsURL(server.URL)
	alerts, err := client.GetAlerts(context.Background())
	if err != nil {
		t.Fatalf("GetAlerts failed: %v", err)
	}

	if len(alerts) != 2 {
		t.Errorf("expected 2 alerts, got %d", len(alerts))
	}
}

func TestFetchAlertsSuccessful(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode([]map[string]string{
			{"alert": "test alert"},
		})
	}))
	defer server.Close()

	client := NewClient(http.DefaultClient).WithAlertsURL(server.URL)
	alerts, err := client.FetchAlerts(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(alerts) != 1 {
		t.Errorf("expected 1 alert, got %d", len(alerts))
	}
}

func TestFetchAlertsGzipDecoding(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		// Create gzipped response
		var buf bytes.Buffer
		gz := gzip.NewWriter(&buf)
		alertData := []map[string]string{{"alert": "gzipped alert"}}
		_ = json.NewEncoder(gz).Encode(alertData)
		_ = gz.Close()

		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Content-Encoding", "gzip")
		_, _ = w.Write(buf.Bytes())
	}))
	defer server.Close()

	client := NewClient(http.DefaultClient).WithAlertsURL(server.URL)
	alerts, err := client.FetchAlerts(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(alerts) != 1 {
		t.Errorf("expected 1 alert, got %d", len(alerts))
	}
}

func TestFetchAlertsRetryThenSuccess(t *testing.T) {
	attempt := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		attempt++
		if attempt < 2 {
			w.WriteHeader(http.StatusServiceUnavailable)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode([]map[string]string{
			{"alert": "success after retry"},
		})
	}))
	defer server.Close()

	client := NewClient(http.DefaultClient).
		WithAlertsURL(server.URL).
		WithRetryDelays([]time.Duration{10 * time.Millisecond, 10 * time.Millisecond})

	alerts, err := client.FetchAlerts(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(alerts) != 1 {
		t.Errorf("expected 1 alert, got %d", len(alerts))
	}
	if attempt != 2 {
		t.Errorf("expected 2 attempts, got %d", attempt)
	}
}

func TestFetchAlertsRetryThenExhausted(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer server.Close()

	client := NewClient(http.DefaultClient).
		WithAlertsURL(server.URL).
		WithRetryDelays([]time.Duration{10 * time.Millisecond, 10 * time.Millisecond})

	alerts, err := client.FetchAlerts(context.Background())

	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if alerts != nil {
		t.Errorf("expected nil alerts, got %v", alerts)
	}
}

func TestGetAlertsReturnsErrorOnFailure(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	client := NewClient(http.DefaultClient).
		WithAlertsURL(server.URL).
		WithRetryDelays([]time.Duration{10 * time.Millisecond})

	alerts, err := client.GetAlerts(context.Background())

	if err == nil {
		t.Error("expected error, got nil")
	}

	if len(alerts) != 0 {
		t.Errorf("expected empty slice, got %d alerts", len(alerts))
	}
}

func TestFetchAlertsErrorDoesNotExposeURL(t *testing.T) {
	// Use a closed port to trigger a connection error
	client := NewClient(http.DefaultClient).
		WithAlertsURL("http://127.0.0.1:1").
		WithRetryDelays([]time.Duration{10 * time.Millisecond})

	_, err := client.FetchAlerts(context.Background())

	if err == nil {
		t.Fatal("expected error, got nil")
	}

	errStr := err.Error()
	// Verify that the error message doesn't contain the URL or query string
	if strings.Contains(errStr, "127.0.0.1") {
		t.Errorf("error message leaked IP address: %s", errStr)
	}
	if strings.Contains(errStr, "cmd=alert") {
		t.Errorf("error message leaked query parameter: %s", errStr)
	}
	if strings.Contains(errStr, "http://") {
		t.Errorf("error message leaked URL scheme: %s", errStr)
	}
}

func TestFetchAlertsEmptyResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte("[]"))
	}))
	defer server.Close()

	client := NewClient(http.DefaultClient).WithAlertsURL(server.URL)
	alerts, err := client.FetchAlerts(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(alerts) != 0 {
		t.Errorf("expected 0 alerts, got %d", len(alerts))
	}
}

func TestFetchAlertsInvalidJSON(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte("not valid json"))
	}))
	defer server.Close()

	client := NewClient(http.DefaultClient).WithAlertsURL(server.URL)
	_, err := client.FetchAlerts(context.Background())

	if err == nil {
		t.Fatal("expected error for invalid JSON, got nil")
	}
}

func TestFetchAlertsHTTPError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	}))
	defer server.Close()

	client := NewClient(http.DefaultClient).WithAlertsURL(server.URL)
	_, err := client.FetchAlerts(context.Background())

	if err == nil {
		t.Fatal("expected error for HTTP 404, got nil")
	}
}

func TestFetchAlertsContextCancellation(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		time.Sleep(100 * time.Millisecond)
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode([]map[string]string{})
	}))
	defer server.Close()

	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	client := NewClient(http.DefaultClient).WithAlertsURL(server.URL)
	_, err := client.FetchAlerts(ctx)

	if err == nil {
		t.Fatal("expected context cancellation error, got nil")
	}
}

func TestFetchAlertsWithBrokenReader(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Content-Length", "1000")
		// Write less data than Content-Length to trigger read error
		_, _ = w.Write([]byte("[]"))
	}))
	defer server.Close()

	client := NewClient(http.DefaultClient).
		WithAlertsURL(server.URL).
		WithRetryDelays([]time.Duration{10 * time.Millisecond})

	_, err := client.FetchAlerts(context.Background())

	// Should return an error when the response body is truncated
	if err == nil {
		t.Fatal("expected error for truncated response body, got nil")
	}
}

// TestScrubURLFromError tests that scrubURLFromError handles nil and non-nil errors correctly.
func TestScrubURLFromError(t *testing.T) {
	tests := []struct {
		name    string
		input   error
		wantNil bool
	}{
		{
			name:    "nil_error",
			input:   nil,
			wantNil: true,
		},
		{
			name:    "non_nil_error",
			input:   xerrors.StockCharts("test error"),
			wantNil: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := scrubURLFromError(tt.input)
			if (result == nil) != tt.wantNil {
				t.Errorf("scrubURLFromError(%v) returned nil=%v, want nil=%v", tt.input, result == nil, tt.wantNil)
			}
		})
	}
}

// TestScrubURLFromErrorPassesThroughContextCancellation tests that context cancellation errors
// are returned unchanged, not scrubbed.
func TestScrubURLFromErrorPassesThroughContextCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	err := ctx.Err()
	result := scrubURLFromError(err)

	// Should return the same error, not a scrubbed generic error
	if !errors.Is(result, context.Canceled) {
		t.Errorf("scrubURLFromError should pass through context.Canceled, got %v", result)
	}
}

// TestScrubURLFromErrorPassesThroughDeadlineExceeded tests that context deadline exceeded errors
// are returned unchanged, not scrubbed.
func TestScrubURLFromErrorPassesThroughDeadlineExceeded(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 0)
	defer cancel()

	// Wait for timeout
	<-ctx.Done()
	err := ctx.Err()
	result := scrubURLFromError(err)

	// Should return the same error, not a scrubbed generic error
	if !errors.Is(result, context.DeadlineExceeded) {
		t.Errorf("scrubURLFromError should pass through context.DeadlineExceeded, got %v", result)
	}
}
