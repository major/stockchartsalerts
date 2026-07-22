// Package xerrors defines error types for stockchartsalerts.
package xerrors

import (
	"errors"
	"fmt"
	"net/http"
)

// Error represents an error from stockchartsalerts.
type Error struct {
	// Kind is the error category.
	Kind Kind
	// Err is the underlying error, if any.
	Err error
	// Service is the service name for HTTP status errors.
	Service string
	// StatusCode is the HTTP status code for HTTP status errors.
	StatusCode int
	// Message is the error message.
	Message string
}

// Kind represents the category of an error.
type Kind string

const (
	// KindAlertPayload indicates a malformed alert payload.
	KindAlertPayload Kind = "alert_payload"
	// KindConfig indicates invalid configuration.
	KindConfig Kind = "config"
	// KindHTTPClient indicates an HTTP client error.
	KindHTTPClient Kind = "http_client"
	// KindHTTPStatus indicates an HTTP status error.
	KindHTTPStatus Kind = "http_status"
	// KindStockCharts indicates a StockCharts error.
	KindStockCharts Kind = "stockcharts"
	// KindTimeParse indicates a timestamp parsing error.
	KindTimeParse Kind = "time_parse"
)

// Error implements the error interface.
func (e *Error) Error() string {
	if e.Message != "" {
		return e.Message
	}
	if e.Err != nil {
		return e.Err.Error()
	}
	return string(e.Kind)
}

// Unwrap returns the underlying error.
func (e *Error) Unwrap() error {
	return e.Err
}

// Is reports whether the error is of the given kind.
func (e *Error) Is(target error) bool {
	t, ok := target.(*Error)
	if !ok {
		return false
	}
	return e.Kind == t.Kind
}

// AlertPayload creates an alert payload error.
func AlertPayload(msg string) error {
	return &Error{
		Kind:    KindAlertPayload,
		Message: fmt.Sprintf("malformed StockCharts alert payload: %s", msg),
	}
}

// Config creates a configuration error.
func Config(msg string) error {
	return &Error{
		Kind:    KindConfig,
		Message: fmt.Sprintf("invalid configuration: %s", msg),
	}
}

// HTTPClient creates an HTTP client error.
func HTTPClient(err error) error {
	return &Error{
		Kind:    KindHTTPClient,
		Err:     err,
		Message: fmt.Sprintf("HTTP client error: %v", err),
	}
}

// HTTPStatus creates an HTTP status error.
func HTTPStatus(service string, statusCode int) error {
	return &Error{
		Kind:       KindHTTPStatus,
		Service:    service,
		StatusCode: statusCode,
		Message:    fmt.Sprintf("%s returned HTTP status %d", service, statusCode),
	}
}

// StockCharts creates a StockCharts error.
func StockCharts(msg string) error {
	return &Error{
		Kind:    KindStockCharts,
		Message: fmt.Sprintf("StockCharts error: %s", msg),
	}
}

// TimeParse creates a timestamp parsing error.
func TimeParse(msg string) error {
	return &Error{
		Kind:    KindTimeParse,
		Message: fmt.Sprintf("failed to parse StockCharts timestamp: %s", msg),
	}
}

// IsAlertPayload reports whether err is an alert payload error.
func IsAlertPayload(err error) bool {
	return errors.Is(err, &Error{Kind: KindAlertPayload})
}

// IsConfig reports whether err is a configuration error.
func IsConfig(err error) bool {
	return errors.Is(err, &Error{Kind: KindConfig})
}

// IsHTTPClient reports whether err is an HTTP client error.
func IsHTTPClient(err error) bool {
	return errors.Is(err, &Error{Kind: KindHTTPClient})
}

// IsHTTPStatus reports whether err is an HTTP status error.
func IsHTTPStatus(err error) bool {
	return errors.Is(err, &Error{Kind: KindHTTPStatus})
}

// IsStockCharts reports whether err is a StockCharts error.
func IsStockCharts(err error) bool {
	return errors.Is(err, &Error{Kind: KindStockCharts})
}

// IsTimeParse reports whether err is a timestamp parsing error.
func IsTimeParse(err error) bool {
	return errors.Is(err, &Error{Kind: KindTimeParse})
}

// EnsureSuccessStatus returns an error if the HTTP status code is not in the 2xx range.
func EnsureSuccessStatus(service string, statusCode int) error {
	if statusCode >= http.StatusOK && statusCode < http.StatusMultipleChoices {
		return nil
	}
	return HTTPStatus(service, statusCode)
}
