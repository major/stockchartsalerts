// Package config provides configuration loading and validation for stockchartsalerts.
package config

import (
	"os"
	"strconv"
	"strings"

	"github.com/major/stockchartsalerts/internal/xerrors"
)

// Settings holds the normalized application configuration.
type Settings struct {
	// MinutesBetweenRuns is the interval in minutes between alert checks (1-1440).
	MinutesBetweenRuns int
	// DiscordWebhookURLs are the Discord webhook URLs to send alerts to.
	DiscordWebhookURLs []string
	// GitCommit is the git commit hash set at build time.
	GitCommit string
	// GitBranch is the git branch name set at build time.
	GitBranch string
}

// Load parses environment variables to create Settings.
// It returns an error if required configuration is missing or invalid.
func Load() (*Settings, error) {
	// Parse minutes between runs from env or use default
	minutesBetweenRuns := 5
	if val, ok := os.LookupEnv("MINUTES_BETWEEN_RUNS"); ok {
		parsed, err := strconv.Atoi(val)
		if err != nil {
			return nil, xerrors.Config("MINUTES_BETWEEN_RUNS must be a valid integer")
		}
		minutesBetweenRuns = parsed
	}

	// Validate minutes between runs
	if minutesBetweenRuns < 1 || minutesBetweenRuns > 1440 {
		return nil, xerrors.Config("minutes-between-runs must be between 1 and 1440")
	}

	// Get webhook URLs from env
	discordWebhookURLs := os.Getenv("DISCORD_WEBHOOK_URLS")

	// Normalize and validate webhook URLs
	webhookURLs := normalizeWebhookURLs(discordWebhookURLs)
	if len(webhookURLs) == 0 {
		return nil, xerrors.Config("at least one Discord webhook URL must be provided via DISCORD_WEBHOOK_URLS")
	}

	// Get git metadata from env or use defaults
	gitCommit := normalizeOptionalValue(os.Getenv("GIT_COMMIT"), "unknown")
	gitBranch := normalizeOptionalValue(os.Getenv("GIT_BRANCH"), "unknown")

	return &Settings{
		MinutesBetweenRuns: minutesBetweenRuns,
		DiscordWebhookURLs: webhookURLs,
		GitCommit:          gitCommit,
		GitBranch:          gitBranch,
	}, nil
}

// Release returns the release string in the format "branch@commit".
func (s *Settings) Release() string {
	return s.GitBranch + "@" + s.GitCommit
}

// normalizeWebhookURLs splits comma-separated URLs, trims whitespace, and deduplicates.
func normalizeWebhookURLs(input string) []string {
	if input == "" {
		return nil
	}

	// Split by comma
	parts := strings.Split(input, ",")

	// Trim, filter empty, and deduplicate
	seen := make(map[string]bool)
	var result []string
	for _, part := range parts {
		trimmed := strings.TrimSpace(part)
		if trimmed != "" && !seen[trimmed] {
			seen[trimmed] = true
			result = append(result, trimmed)
		}
	}

	return result
}

// normalizeOptionalValue returns the trimmed value if non-empty, otherwise the default.
func normalizeOptionalValue(value, defaultValue string) string {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return defaultValue
	}
	return trimmed
}
