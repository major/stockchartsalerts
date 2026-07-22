package httpx

import (
	"net/http"
	"testing"
	"time"

	"github.com/major/stockchartsalerts/internal/xerrors"
)

func TestNewClient(t *testing.T) {
	client := NewClient()
	if client == nil {
		t.Fatal("expected client, got nil")
	}
	if client.Timeout != HTTPTimeout {
		t.Errorf("expected timeout %v, got %v", HTTPTimeout, client.Timeout)
	}
	if client.Transport == nil {
		t.Fatal("expected transport, got nil")
	}
}

func TestEnsureSuccessStatus(t *testing.T) {
	tests := []struct {
		name       string
		service    string
		statusCode int
		wantErr    bool
	}{
		{"OK", "TestService", 200, false},
		{"Created", "TestService", 201, false},
		{"NoContent", "TestService", 204, false},
		{"BadRequest", "TestService", 400, true},
		{"Unauthorized", "TestService", 401, true},
		{"Forbidden", "TestService", 403, true},
		{"NotFound", "TestService", 404, true},
		{"InternalServerError", "TestService", 500, true},
		{"BadGateway", "TestService", 502, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := EnsureSuccessStatus(tt.service, tt.statusCode)
			if (err != nil) != tt.wantErr {
				t.Errorf("EnsureSuccessStatus() error = %v, wantErr %v", err, tt.wantErr)
			}
			if err != nil && !xerrors.IsHTTPStatus(err) {
				t.Errorf("expected HTTPStatus error, got %T", err)
			}
		})
	}
}

func TestHTTPTimeoutConstant(t *testing.T) {
	if HTTPTimeout != 30*time.Second {
		t.Errorf("expected HTTPTimeout to be 30s, got %v", HTTPTimeout)
	}
}

func TestLimitRedirects(t *testing.T) {
	checkRedirect := limitRedirects(2)

	// Test with no prior redirects
	req := &http.Request{}
	err := checkRedirect(req, []*http.Request{})
	if err != nil {
		t.Errorf("expected no error for 0 redirects, got %v", err)
	}

	// Test with one prior redirect
	err = checkRedirect(req, []*http.Request{{}})
	if err != nil {
		t.Errorf("expected no error for 1 redirect, got %v", err)
	}

	// Test with two prior redirects (at limit)
	err = checkRedirect(req, []*http.Request{{}, {}})
	if err != http.ErrUseLastResponse {
		t.Errorf("expected ErrUseLastResponse at limit, got %v", err)
	}
}
