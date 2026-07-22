// Package telemetry provides logging and observability utilities for stockchartsalerts.
package telemetry

import (
	"log/slog"
	"os"
	"strings"
)

// InitLogging initializes the default slog logger with JSON output.
// The log level can be overridden via the LOG_LEVEL environment variable
// (valid values: debug, info, warn, error; defaults to info).
func InitLogging() {
	level := slog.LevelInfo

	// Check for LOG_LEVEL environment variable
	if levelStr, ok := os.LookupEnv("LOG_LEVEL"); ok {
		levelStr = strings.ToLower(strings.TrimSpace(levelStr))
		switch levelStr {
		case "debug":
			level = slog.LevelDebug
		case "info":
			level = slog.LevelInfo
		case "warn":
			level = slog.LevelWarn
		case "error":
			level = slog.LevelError
		}
	}

	// Create a JSON handler writing to stdout
	handler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: level,
	})

	// Set as the default logger
	slog.SetDefault(slog.New(handler))
}
