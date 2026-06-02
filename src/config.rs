//! Configuration loaded from command-line flags and environment variables.

use std::collections::HashSet;

use clap::Parser;
use tracing::info;

use crate::{Error, Result};

/// Raw command-line and environment configuration.
#[derive(Debug, Parser)]
#[command(version, about, long_about = None)]
pub struct Cli {
    /// Minutes to wait between alert checks.
    #[arg(long, env = "MINUTES_BETWEEN_RUNS", default_value_t = 5, value_parser = clap::value_parser!(u16).range(1..=1440))]
    pub minutes_between_runs: u16,

    /// Comma-separated Discord webhook URLs.
    #[arg(long, env = "DISCORD_WEBHOOK_URLS", value_delimiter = ',')]
    pub discord_webhook_urls: Vec<String>,

    /// Sentry DSN for error tracking.
    #[arg(long, env = "SENTRY_DSN", default_value = "")]
    pub sentry_dsn: String,

    /// Sentry environment name.
    #[arg(long, env = "SENTRY_ENVIRONMENT", default_value = "production")]
    pub sentry_environment: String,

    /// Git commit hash set at build time.
    #[arg(long, env = "GIT_COMMIT", default_value = "unknown")]
    pub git_commit: String,

    /// Git branch name set at build time.
    #[arg(long, env = "GIT_BRANCH", default_value = "unknown")]
    pub git_branch: String,
}

impl Cli {
    /// Parse command-line and environment configuration.
    #[must_use]
    pub fn parse() -> Self {
        <Self as Parser>::parse()
    }
}

/// Normalized application settings.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Settings {
    /// Minutes to wait between alert checks.
    pub minutes_between_runs: u16,
    /// Discord webhook URLs with whitespace removed and duplicates dropped.
    pub discord_webhook_urls: Vec<String>,
    /// Sentry DSN for error tracking.
    pub sentry_dsn: String,
    /// Sentry environment name.
    pub sentry_environment: String,
    /// Git commit hash set at build time.
    pub git_commit: String,
    /// Git branch name set at build time.
    pub git_branch: String,
}

impl Settings {
    /// Build settings from parsed command-line and environment values.
    ///
    /// # Errors
    ///
    /// Returns an error when no Discord webhook URL is configured.
    pub fn from_cli(cli: Cli) -> Result<Self> {
        let discord_webhook_urls = normalize_webhook_urls(cli.discord_webhook_urls);

        if discord_webhook_urls.is_empty() {
            return Err(Error::Config(
                "at least one Discord webhook URL must be provided via DISCORD_WEBHOOK_URLS"
                    .to_string(),
            ));
        }

        Ok(Self {
            minutes_between_runs: cli.minutes_between_runs,
            discord_webhook_urls,
            sentry_dsn: cli.sentry_dsn.trim().to_string(),
            sentry_environment: normalize_optional_value(&cli.sentry_environment, "production"),
            git_commit: normalize_optional_value(&cli.git_commit, "unknown"),
            git_branch: normalize_optional_value(&cli.git_branch, "unknown"),
        })
    }

    /// Return the Sentry release string as `<branch>@<commit>`.
    #[must_use]
    pub fn release(&self) -> String {
        format!("{}@{}", self.git_branch, self.git_commit)
    }

    /// Return useful release metadata for Sentry when build metadata is known.
    #[must_use]
    pub fn sentry_release(&self) -> Option<String> {
        match (
            known_metadata(&self.git_branch),
            known_metadata(&self.git_commit),
        ) {
            (Some(branch), Some(commit)) => Some(format!("{branch}@{commit}")),
            (_, Some(commit)) => Some(commit.to_string()),
            (_, None) => None,
        }
    }

    /// Log non-secret settings with webhook URL values masked.
    pub fn log_safe(&self) {
        info!(
            minutes_between_runs = self.minutes_between_runs,
            "configuration loaded"
        );
        info!(
            discord_webhooks = self.discord_webhook_urls.len(),
            "Discord webhooks configured"
        );
        info!(
            sentry_enabled = !self.sentry_dsn.is_empty(),
            "Sentry configuration loaded"
        );
        info!(sentry_environment = %self.sentry_environment, "Sentry environment configured");
        info!(git_commit = %self.git_commit, git_branch = %self.git_branch, "version metadata loaded");
    }
}

fn normalize_webhook_urls(urls: Vec<String>) -> Vec<String> {
    let mut seen = HashSet::new();
    let mut normalized = Vec::new();

    urls.into_iter()
        .flat_map(|value| {
            value
                .split(',')
                .map(str::trim)
                .map(str::to_owned)
                .collect::<Vec<_>>()
        })
        .filter(|value| !value.is_empty())
        .for_each(|value| {
            if seen.insert(value.clone()) {
                normalized.push(value);
            }
        });

    normalized
}

fn normalize_optional_value(value: &str, default: &str) -> String {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        default.to_string()
    } else {
        trimmed.to_string()
    }
}

fn known_metadata(value: &str) -> Option<&str> {
    let trimmed = value.trim();
    if trimmed.is_empty() || trimmed == "unknown" {
        None
    } else {
        Some(trimmed)
    }
}

#[cfg(test)]
mod tests {
    use clap::Parser;

    use super::{Cli, Settings};

    const WEBHOOK_URL: &str = "https://discord.com/api/webhooks/123/abc";

    fn cli_with_urls(webhook_urls: Vec<&str>) -> Cli {
        Cli {
            minutes_between_runs: 5,
            discord_webhook_urls: webhook_urls.into_iter().map(str::to_owned).collect(),
            sentry_dsn: String::new(),
            sentry_environment: "production".to_string(),
            git_commit: "abc123".to_string(),
            git_branch: "main".to_string(),
        }
    }

    fn parse_cli(args: &[&str]) -> clap::error::Result<Cli> {
        let mut all_args = vec!["stockchartsalerts"];
        all_args.extend_from_slice(args);

        Cli::try_parse_from(all_args)
    }

    #[test]
    fn cli_minutes_between_runs_defaults_to_five() {
        let cli = parse_cli(&["--discord-webhook-urls", WEBHOOK_URL])
            .expect("default interval should parse");

        assert_eq!(cli.minutes_between_runs, 5);
    }

    #[test]
    fn cli_minutes_between_runs_accepts_bounds() {
        let minimum = parse_cli(&[
            "--minutes-between-runs",
            "1",
            "--discord-webhook-urls",
            WEBHOOK_URL,
        ])
        .expect("minimum interval should parse");
        let maximum = parse_cli(&[
            "--minutes-between-runs",
            "1440",
            "--discord-webhook-urls",
            WEBHOOK_URL,
        ])
        .expect("maximum interval should parse");

        assert_eq!(minimum.minutes_between_runs, 1);
        assert_eq!(maximum.minutes_between_runs, 1440);
    }

    #[test]
    fn cli_minutes_between_runs_rejects_values_outside_bounds() {
        assert!(
            parse_cli(&[
                "--minutes-between-runs",
                "0",
                "--discord-webhook-urls",
                WEBHOOK_URL,
            ])
            .is_err()
        );
        assert!(
            parse_cli(&[
                "--minutes-between-runs",
                "1441",
                "--discord-webhook-urls",
                WEBHOOK_URL,
            ])
            .is_err()
        );
    }

    #[test]
    fn settings_normalize_multiple_webhook_urls() {
        let settings = Settings::from_cli(cli_with_urls(vec![
            "https://discord.com/api/webhooks/1/abc , https://discord.com/api/webhooks/2/def",
        ]))
        .expect("webhook URLs should be accepted");

        assert_eq!(
            settings.discord_webhook_urls,
            vec![
                "https://discord.com/api/webhooks/1/abc",
                "https://discord.com/api/webhooks/2/def"
            ]
        );
    }

    #[test]
    fn settings_deduplicate_webhook_urls() {
        let settings = Settings::from_cli(cli_with_urls(vec![
            "https://discord.com/api/webhooks/123/abc",
            "https://discord.com/api/webhooks/123/abc",
            "https://discord.com/api/webhooks/456/def",
        ]))
        .expect("webhook URLs should be accepted");

        assert_eq!(
            settings.discord_webhook_urls,
            vec![
                "https://discord.com/api/webhooks/123/abc",
                "https://discord.com/api/webhooks/456/def"
            ]
        );
    }

    #[test]
    fn settings_reject_missing_webhook_urls() {
        let error = Settings::from_cli(cli_with_urls(vec![])).expect_err("missing URL should fail");

        assert!(
            error
                .to_string()
                .contains("at least one Discord webhook URL")
        );
    }

    #[test]
    fn settings_release_matches_legacy_format() {
        let settings = Settings::from_cli(cli_with_urls(vec![
            "https://discord.com/api/webhooks/123/abc",
        ]))
        .expect("settings should be valid");

        assert_eq!(settings.release(), "main@abc123");
    }

    #[test]
    fn settings_trim_sentry_metadata() {
        let mut cli = cli_with_urls(vec![WEBHOOK_URL]);
        cli.sentry_dsn = "  https://public@example.com/1  ".to_string();
        cli.sentry_environment = " production ".to_string();
        cli.git_commit = " abc123 ".to_string();
        cli.git_branch = " main ".to_string();

        let settings = Settings::from_cli(cli).expect("settings should be valid");

        assert_eq!(settings.sentry_dsn, "https://public@example.com/1");
        assert_eq!(settings.sentry_environment, "production");
        assert_eq!(settings.release(), "main@abc123");
    }

    #[test]
    fn settings_default_empty_sentry_environment_and_metadata() {
        let mut cli = cli_with_urls(vec![WEBHOOK_URL]);
        cli.sentry_environment = "   ".to_string();
        cli.git_commit = "   ".to_string();
        cli.git_branch = "   ".to_string();

        let settings = Settings::from_cli(cli).expect("settings should be valid");

        assert_eq!(settings.sentry_environment, "production");
        assert_eq!(settings.release(), "unknown@unknown");
        assert_eq!(settings.sentry_release(), None);
    }

    #[test]
    fn settings_sentry_release_uses_available_metadata() {
        let mut settings =
            Settings::from_cli(cli_with_urls(vec![WEBHOOK_URL])).expect("settings should be valid");

        assert_eq!(settings.sentry_release().as_deref(), Some("main@abc123"));

        settings.git_branch = "unknown".to_string();
        assert_eq!(settings.sentry_release().as_deref(), Some("abc123"));

        settings.git_commit = "unknown".to_string();
        assert_eq!(settings.sentry_release(), None);

        settings.git_branch = "main".to_string();
        assert_eq!(settings.sentry_release(), None);
    }
}
