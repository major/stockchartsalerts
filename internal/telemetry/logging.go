// Package telemetry provides logging and observability utilities for stockchartsalerts.
package telemetry

import (
	"log/slog"
	"os"
	"strings"
)

// parseLogLevel converts a LOG_LEVEL string into an slog.Level, defaulting to Info for empty or unrecognized values.
func parseLogLevel(value string) slog.Level {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "debug":
		return slog.LevelDebug
	case "warn":
		return slog.LevelWarn
	case "error":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}

// InitLogging initializes the default slog logger with plain text output.
// The log level can be overridden via the LOG_LEVEL environment variable
// (valid values: debug, info, warn, error; defaults to info).
func InitLogging() {
	level := parseLogLevel(os.Getenv("LOG_LEVEL"))

	// Create a text handler writing to stdout
	handler := slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{
		Level: level,
	})

	// Set as the default logger
	slog.SetDefault(slog.New(handler))
}
