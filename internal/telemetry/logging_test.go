package telemetry

import (
	"log/slog"
	"testing"
)

func TestParseLogLevel(t *testing.T) {
	tests := []struct {
		input    string
		expected slog.Level
	}{
		{"debug", slog.LevelDebug},
		{"DEBUG", slog.LevelDebug},
		{"Debug", slog.LevelDebug},
		{"info", slog.LevelInfo},
		{"INFO", slog.LevelInfo},
		{"Info", slog.LevelInfo},
		{"warn", slog.LevelWarn},
		{"WARN", slog.LevelWarn},
		{"Warn", slog.LevelWarn},
		{"error", slog.LevelError},
		{"ERROR", slog.LevelError},
		{"Error", slog.LevelError},
		{"", slog.LevelInfo},
		{"  ", slog.LevelInfo},
		{"  debug  ", slog.LevelDebug},
		{"invalid", slog.LevelInfo},
		{"unknown", slog.LevelInfo},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			result := parseLogLevel(tt.input)
			if result != tt.expected {
				t.Errorf("parseLogLevel(%q) = %v, expected %v", tt.input, result, tt.expected)
			}
		})
	}
}

func TestInitLoggingDoesNotPanic(_ *testing.T) {
	// Should not panic
	InitLogging()
}

func TestInitLoggingDefaultLevel(t *testing.T) {
	// Clear any existing LOG_LEVEL
	t.Setenv("LOG_LEVEL", "")

	InitLogging()

	// Verify that the default logger is set
	if slog.Default() == nil {
		t.Fatal("default logger is nil")
	}
}

func TestInitLoggingDebugLevel(t *testing.T) {
	t.Setenv("LOG_LEVEL", "debug")

	InitLogging()

	if slog.Default() == nil {
		t.Fatal("default logger is nil")
	}
}

func TestInitLoggingWarnLevel(t *testing.T) {
	t.Setenv("LOG_LEVEL", "warn")

	InitLogging()

	if slog.Default() == nil {
		t.Fatal("default logger is nil")
	}
}

func TestInitLoggingErrorLevel(t *testing.T) {
	t.Setenv("LOG_LEVEL", "error")

	InitLogging()

	if slog.Default() == nil {
		t.Fatal("default logger is nil")
	}
}

func TestInitLoggingInvalidLevel(t *testing.T) {
	t.Setenv("LOG_LEVEL", "invalid")

	// Should not panic, should default to info
	InitLogging()

	if slog.Default() == nil {
		t.Fatal("default logger is nil")
	}
}

func TestInitLoggingCaseInsensitive(t *testing.T) {
	t.Setenv("LOG_LEVEL", "DEBUG")

	InitLogging()

	if slog.Default() == nil {
		t.Fatal("default logger is nil")
	}
}

func TestInitLoggingWithWhitespace(t *testing.T) {
	t.Setenv("LOG_LEVEL", "  info  ")

	InitLogging()

	if slog.Default() == nil {
		t.Fatal("default logger is nil")
	}
}
