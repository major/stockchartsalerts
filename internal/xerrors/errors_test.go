package xerrors

import (
	"errors"
	"strings"
	"testing"
)

func TestAlertPayloadError(t *testing.T) {
	err := AlertPayload("invalid field")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !IsAlertPayload(err) {
		t.Errorf("IsAlertPayload failed")
	}
	if msg := err.Error(); msg != "malformed StockCharts alert payload: invalid field" {
		t.Errorf("unexpected message: %s", msg)
	}
}

func TestConfigError(t *testing.T) {
	err := Config("missing webhook URL")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !IsConfig(err) {
		t.Errorf("IsConfig failed")
	}
	if msg := err.Error(); msg != "invalid configuration: missing webhook URL" {
		t.Errorf("unexpected message: %s", msg)
	}
}

func TestHTTPClientError(t *testing.T) {
	underlying := errors.New("connection refused")
	err := HTTPClient(underlying)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !IsHTTPClient(err) {
		t.Errorf("IsHTTPClient failed")
	}
	if !errors.Is(err, underlying) {
		t.Errorf("expected underlying error to be wrapped")
	}
}

func TestHTTPStatusError(t *testing.T) {
	err := HTTPStatus("Discord", 502)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !IsHTTPStatus(err) {
		t.Errorf("IsHTTPStatus failed")
	}
	if msg := err.Error(); msg != "Discord returned HTTP status 502" {
		t.Errorf("unexpected message: %s", msg)
	}
}

func TestStockChartsError(t *testing.T) {
	err := StockCharts("rate limited")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !IsStockCharts(err) {
		t.Errorf("IsStockCharts failed")
	}
	if msg := err.Error(); msg != "StockCharts error: rate limited" {
		t.Errorf("unexpected message: %s", msg)
	}
}

func TestTimeParseError(t *testing.T) {
	err := TimeParse("invalid format")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !IsTimeParse(err) {
		t.Errorf("IsTimeParse failed")
	}
	if msg := err.Error(); msg != "failed to parse StockCharts timestamp: invalid format" {
		t.Errorf("unexpected message: %s", msg)
	}
}

func TestEnsureSuccessStatus(t *testing.T) {
	tests := []struct {
		name       string
		statusCode int
		wantErr    bool
	}{
		{"OK", 200, false},
		{"Created", 201, false},
		{"NoContent", 204, false},
		{"BadRequest", 400, true},
		{"Unauthorized", 401, true},
		{"Forbidden", 403, true},
		{"NotFound", 404, true},
		{"InternalServerError", 500, true},
		{"BadGateway", 502, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := EnsureSuccessStatus("TestService", tt.statusCode)
			if (err != nil) != tt.wantErr {
				t.Errorf("EnsureSuccessStatus() error = %v, wantErr %v", err, tt.wantErr)
			}
			if err != nil && !IsHTTPStatus(err) {
				t.Errorf("expected HTTPStatus error, got %T", err)
			}
		})
	}
}

func TestErrorUnwrap(t *testing.T) {
	underlying := errors.New("underlying error")
	err := HTTPClient(underlying)
	if !errors.Is(err, underlying) {
		t.Errorf("Unwrap failed to expose underlying error")
	}
}

func TestErrorIs(t *testing.T) {
	err := AlertPayload("test")
	if !errors.Is(err, &Error{Kind: KindAlertPayload}) {
		t.Errorf("Is() failed for matching kind")
	}
	if errors.Is(err, &Error{Kind: KindConfig}) {
		t.Errorf("Is() should not match different kind")
	}
	if errors.Is(err, errors.New("other")) {
		t.Errorf("Is() should not match non-Error types")
	}
}

func TestErrorErrorMethod(t *testing.T) {
	// Test with message
	err1 := AlertPayload("test")
	if msg := err1.Error(); msg != "malformed StockCharts alert payload: test" {
		t.Errorf("expected message, got %q", msg)
	}

	// Test with underlying error
	underlying := errors.New("underlying")
	err2 := HTTPClient(underlying)
	if msg := err2.Error(); !strings.Contains(msg, "underlying") {
		t.Errorf("expected underlying error in message, got %q", msg)
	}

	// Test with kind only (no message, no error)
	err3 := &Error{Kind: KindAlertPayload}
	if msg := err3.Error(); msg != string(KindAlertPayload) {
		t.Errorf("expected kind string, got %q", msg)
	}

	// Test with error but no message (should use error's message)
	err4 := &Error{Kind: KindHTTPClient, Err: errors.New("test error")}
	if msg := err4.Error(); msg != "test error" {
		t.Errorf("expected error message, got %q", msg)
	}
}

func TestIsHelpers(t *testing.T) {
	tests := []struct {
		name   string
		err    error
		checks map[string]bool
	}{
		{
			name: "AlertPayload",
			err:  AlertPayload("test"),
			checks: map[string]bool{
				"IsAlertPayload": true,
				"IsConfig":       false,
				"IsHTTPClient":   false,
				"IsHTTPStatus":   false,
				"IsStockCharts":  false,
				"IsTimeParse":    false,
			},
		},
		{
			name: "Config",
			err:  Config("test"),
			checks: map[string]bool{
				"IsAlertPayload": false,
				"IsConfig":       true,
				"IsHTTPClient":   false,
				"IsHTTPStatus":   false,
				"IsStockCharts":  false,
				"IsTimeParse":    false,
			},
		},
		{
			name: "HTTPClient",
			err:  HTTPClient(errors.New("test")),
			checks: map[string]bool{
				"IsAlertPayload": false,
				"IsConfig":       false,
				"IsHTTPClient":   true,
				"IsHTTPStatus":   false,
				"IsStockCharts":  false,
				"IsTimeParse":    false,
			},
		},
		{
			name: "HTTPStatus",
			err:  HTTPStatus("Test", 500),
			checks: map[string]bool{
				"IsAlertPayload": false,
				"IsConfig":       false,
				"IsHTTPClient":   false,
				"IsHTTPStatus":   true,
				"IsStockCharts":  false,
				"IsTimeParse":    false,
			},
		},
		{
			name: "StockCharts",
			err:  StockCharts("test"),
			checks: map[string]bool{
				"IsAlertPayload": false,
				"IsConfig":       false,
				"IsHTTPClient":   false,
				"IsHTTPStatus":   false,
				"IsStockCharts":  true,
				"IsTimeParse":    false,
			},
		},
		{
			name: "TimeParse",
			err:  TimeParse("test"),
			checks: map[string]bool{
				"IsAlertPayload": false,
				"IsConfig":       false,
				"IsHTTPClient":   false,
				"IsHTTPStatus":   false,
				"IsStockCharts":  false,
				"IsTimeParse":    true,
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.checks["IsAlertPayload"] != IsAlertPayload(tt.err) {
				t.Errorf("IsAlertPayload mismatch")
			}
			if tt.checks["IsConfig"] != IsConfig(tt.err) {
				t.Errorf("IsConfig mismatch")
			}
			if tt.checks["IsHTTPClient"] != IsHTTPClient(tt.err) {
				t.Errorf("IsHTTPClient mismatch")
			}
			if tt.checks["IsHTTPStatus"] != IsHTTPStatus(tt.err) {
				t.Errorf("IsHTTPStatus mismatch")
			}
			if tt.checks["IsStockCharts"] != IsStockCharts(tt.err) {
				t.Errorf("IsStockCharts mismatch")
			}
			if tt.checks["IsTimeParse"] != IsTimeParse(tt.err) {
				t.Errorf("IsTimeParse mismatch")
			}
		})
	}
}
