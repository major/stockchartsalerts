package config

import (
	"strings"
	"testing"
)

func TestNormalizeWebhookURLs(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected []string
	}{
		{
			name:     "single URL",
			input:    "https://discord.com/api/webhooks/123/abc",
			expected: []string{"https://discord.com/api/webhooks/123/abc"},
		},
		{
			name:     "multiple URLs comma-separated",
			input:    "https://discord.com/api/webhooks/1/abc,https://discord.com/api/webhooks/2/def",
			expected: []string{"https://discord.com/api/webhooks/1/abc", "https://discord.com/api/webhooks/2/def"},
		},
		{
			name:     "URLs with whitespace",
			input:    "https://discord.com/api/webhooks/1/abc , https://discord.com/api/webhooks/2/def",
			expected: []string{"https://discord.com/api/webhooks/1/abc", "https://discord.com/api/webhooks/2/def"},
		},
		{
			name:     "deduplicate URLs",
			input:    "https://discord.com/api/webhooks/123/abc,https://discord.com/api/webhooks/123/abc",
			expected: []string{"https://discord.com/api/webhooks/123/abc"},
		},
		{
			name:     "empty string",
			input:    "",
			expected: nil,
		},
		{
			name:     "only whitespace",
			input:    "   ,   ,   ",
			expected: nil,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := normalizeWebhookURLs(tt.input)
			if len(result) != len(tt.expected) {
				t.Errorf("expected %d URLs, got %d", len(tt.expected), len(result))
			}
			for i, url := range result {
				if i >= len(tt.expected) || url != tt.expected[i] {
					t.Errorf("URL mismatch at index %d: expected %q, got %q", i, tt.expected[i], url)
				}
			}
		})
	}
}

func TestNormalizeOptionalValue(t *testing.T) {
	tests := []struct {
		name         string
		value        string
		defaultValue string
		expected     string
	}{
		{"non-empty value", "main", "unknown", "main"},
		{"empty value", "", "unknown", "unknown"},
		{"whitespace value", "   ", "unknown", "unknown"},
		{"value with leading/trailing space", "  main  ", "unknown", "main"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := normalizeOptionalValue(tt.value, tt.defaultValue)
			if result != tt.expected {
				t.Errorf("expected %q, got %q", tt.expected, result)
			}
		})
	}
}

func TestSettingsRelease(t *testing.T) {
	settings := &Settings{
		GitBranch: "main",
		GitCommit: "abc123",
	}
	expected := "main@abc123"
	if result := settings.Release(); result != expected {
		t.Errorf("expected %q, got %q", expected, result)
	}
}

func TestLoadWithEnvVars(t *testing.T) {
	// Test with valid env vars
	t.Setenv("MINUTES_BETWEEN_RUNS", "10")
	t.Setenv("DISCORD_WEBHOOK_URLS", "https://discord.com/api/webhooks/123/abc")
	t.Setenv("GIT_COMMIT", "def456")
	t.Setenv("GIT_BRANCH", "develop")

	settings, err := Load()
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}

	if settings.MinutesBetweenRuns != 10 {
		t.Errorf("expected MinutesBetweenRuns=10, got %d", settings.MinutesBetweenRuns)
	}
	if len(settings.DiscordWebhookURLs) != 1 || settings.DiscordWebhookURLs[0] != "https://discord.com/api/webhooks/123/abc" {
		t.Errorf("unexpected webhook URLs: %v", settings.DiscordWebhookURLs)
	}
	if settings.GitCommit != "def456" {
		t.Errorf("expected GitCommit=def456, got %s", settings.GitCommit)
	}
	if settings.GitBranch != "develop" {
		t.Errorf("expected GitBranch=develop, got %s", settings.GitBranch)
	}
}

func TestLoadMissingWebhookURLs(t *testing.T) {
	t.Setenv("DISCORD_WEBHOOK_URLS", "")

	_, err := Load()
	if err == nil {
		t.Fatal("expected error for missing webhook URLs")
	}
	if msg := err.Error(); !strings.Contains(msg, "at least one Discord webhook URL") {
		t.Errorf("unexpected error message: %s", msg)
	}
}

func TestLoadInvalidMinutes(t *testing.T) {
	tests := []struct {
		name  string
		value string
	}{
		{"below minimum", "0"},
		{"above maximum", "1441"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Setenv("MINUTES_BETWEEN_RUNS", tt.value)
			t.Setenv("DISCORD_WEBHOOK_URLS", "https://discord.com/api/webhooks/123/abc")

			_, err := Load()
			if err == nil {
				t.Fatal("expected error for invalid minutes")
			}
			if msg := err.Error(); !strings.Contains(msg, "must be between 1 and 1440") {
				t.Errorf("unexpected error message: %s", msg)
			}
		})
	}
}

func TestLoadInvalidMinutesFormat(t *testing.T) {
	t.Setenv("MINUTES_BETWEEN_RUNS", "not-a-number")
	t.Setenv("DISCORD_WEBHOOK_URLS", "https://discord.com/api/webhooks/123/abc")

	_, err := Load()
	if err == nil {
		t.Fatal("expected error for invalid minutes format")
	}
	if msg := err.Error(); !strings.Contains(msg, "must be a valid integer") {
		t.Errorf("unexpected error message: %s", msg)
	}
}

func TestLoadDefaultValues(t *testing.T) {
	// Only set the required webhook URL; other vars will use defaults
	t.Setenv("DISCORD_WEBHOOK_URLS", "https://discord.com/api/webhooks/123/abc")

	settings, err := Load()
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}

	if settings.MinutesBetweenRuns != 5 {
		t.Errorf("expected default MinutesBetweenRuns=5, got %d", settings.MinutesBetweenRuns)
	}
	if settings.GitCommit != "unknown" {
		t.Errorf("expected default GitCommit=unknown, got %s", settings.GitCommit)
	}
	if settings.GitBranch != "unknown" {
		t.Errorf("expected default GitBranch=unknown, got %s", settings.GitBranch)
	}
}
