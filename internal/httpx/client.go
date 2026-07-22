// Package httpx provides HTTP client utilities for stockchartsalerts.
package httpx

import (
	"net"
	"net/http"
	"time"

	"github.com/major/stockchartsalerts/internal/xerrors"
)

// HTTPTimeout is the timeout for HTTP requests.
const HTTPTimeout = 30 * time.Second

// NewClient builds a shared HTTP client with production defaults.
// The client has a 30-second request timeout, 5 max idle connections per host,
// 30-second idle pool timeout, and a 10-redirect limit.
func NewClient() *http.Client {
	transport := &http.Transport{
		MaxIdleConnsPerHost: 5,
		IdleConnTimeout:     30 * time.Second,
		DialContext: (&net.Dialer{
			Timeout: HTTPTimeout,
		}).DialContext,
	}

	client := &http.Client{
		Timeout:       HTTPTimeout,
		Transport:     transport,
		CheckRedirect: limitRedirects(10),
	}

	return client
}

// limitRedirects returns a CheckRedirect function that limits redirects to n.
func limitRedirects(n int) func(*http.Request, []*http.Request) error {
	return func(_ *http.Request, via []*http.Request) error {
		if len(via) >= n {
			return http.ErrUseLastResponse
		}
		return nil
	}
}

// EnsureSuccessStatus returns an error if the HTTP status code is not in the 2xx range.
func EnsureSuccessStatus(service string, statusCode int) error {
	return xerrors.EnsureSuccessStatus(service, statusCode)
}
