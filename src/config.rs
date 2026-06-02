//! Configuration loaded from command-line flags and environment variables.

use std::collections::HashSet;

use clap::Parser;

use crate::{Error, Result};

/// Raw command-line and environment configuration.
#[derive(Debug, Parser)]
#[command(version, about, long_about = None)]
pub struct Cli {
    /// Minutes to wait between alert checks.
    #[arg(long, env = "MINUTES_BETWEEN_RUNS", default_value_t = 5, value_parser = clap::value_parser!(u16).range(1..=1440))]
    pub minutes_between_runs: u16,

    /// Discord webhook URL, deprecated in favor of DISCORD_WEBHOOK_URLS.
    #[arg(long, env = "DISCORD_WEBHOOK_URL")]
    pub discord_webhook_url: Option<String>,

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
        let discord_webhook_urls =
            normalize_webhook_urls(cli.discord_webhook_url, cli.discord_webhook_urls);

        if discord_webhook_urls.is_empty() {
            return Err(Error::Config(
                "at least one Discord webhook URL must be provided via DISCORD_WEBHOOK_URL or DISCORD_WEBHOOK_URLS"
                    .to_string(),
            ));
        }

        Ok(Self {
            minutes_between_runs: cli.minutes_between_runs,
            discord_webhook_urls,
            sentry_dsn: cli.sentry_dsn,
            sentry_environment: cli.sentry_environment,
            git_commit: cli.git_commit,
            git_branch: cli.git_branch,
        })
    }

    /// Return the Sentry release string used by the Python app.
    #[must_use]
    pub fn release(&self) -> String {
        format!("{}@{}", self.git_branch, self.git_commit)
    }
}

fn normalize_webhook_urls(legacy_url: Option<String>, urls: Vec<String>) -> Vec<String> {
    let mut seen = HashSet::new();
    let mut normalized = Vec::new();

    legacy_url
        .into_iter()
        .chain(urls)
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

#[cfg(test)]
mod tests {
    use super::{Cli, Settings};

    fn cli_with_urls(legacy_url: Option<&str>, webhook_urls: Vec<&str>) -> Cli {
        Cli {
            minutes_between_runs: 5,
            discord_webhook_url: legacy_url.map(str::to_owned),
            discord_webhook_urls: webhook_urls.into_iter().map(str::to_owned).collect(),
            sentry_dsn: String::new(),
            sentry_environment: "production".to_string(),
            git_commit: "abc123".to_string(),
            git_branch: "main".to_string(),
        }
    }

    #[test]
    fn settings_accept_legacy_webhook_url() {
        let settings = Settings::from_cli(cli_with_urls(
            Some("https://discord.com/api/webhooks/123/abc"),
            vec![],
        ))
        .expect("legacy webhook URL should be accepted");

        assert_eq!(
            settings.discord_webhook_urls,
            vec!["https://discord.com/api/webhooks/123/abc"]
        );
    }

    #[test]
    fn settings_normalize_multiple_webhook_urls() {
        let settings = Settings::from_cli(cli_with_urls(
            None,
            vec!["https://discord.com/api/webhooks/1/abc , https://discord.com/api/webhooks/2/def"],
        ))
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
        let settings = Settings::from_cli(cli_with_urls(
            Some("https://discord.com/api/webhooks/123/abc"),
            vec![
                "https://discord.com/api/webhooks/123/abc",
                "https://discord.com/api/webhooks/456/def",
            ],
        ))
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
        let error =
            Settings::from_cli(cli_with_urls(None, vec![])).expect_err("missing URL should fail");

        assert!(
            error
                .to_string()
                .contains("at least one Discord webhook URL")
        );
    }

    #[test]
    fn settings_release_matches_python_format() {
        let settings = Settings::from_cli(cli_with_urls(
            Some("https://discord.com/api/webhooks/123/abc"),
            vec![],
        ))
        .expect("settings should be valid");

        assert_eq!(settings.release(), "main@abc123");
    }
}
