// Package main is the binary entry point for stockchartsalerts.
package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/major/stockchartsalerts/internal/app"
	"github.com/major/stockchartsalerts/internal/config"
	"github.com/major/stockchartsalerts/internal/telemetry"
)

func main() {
	// Initialize logging
	telemetry.InitLogging()

	// Load configuration from environment
	settings, err := config.Load()
	if err != nil {
		slog.Error("failed to load configuration", "error", err)
		os.Exit(1)
	}

	// Build the application
	application := app.New(*settings)

	// Create a context that is cancelled on SIGINT or SIGTERM
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	// Run the scheduler until shutdown
	if err := application.RunUntilShutdown(ctx); err != nil && err != context.Canceled {
		slog.Error("application error", "error", err)
		os.Exit(1)
	}

	os.Exit(0)
}
