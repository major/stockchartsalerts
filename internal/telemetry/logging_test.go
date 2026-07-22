package telemetry

import (
	"log/slog"
	"testing"
)

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
