//! Logging and Sentry initialization.

use std::time::Duration;

use sentry::{ClientInitGuard, ClientOptions, types::Dsn};
use tracing::warn;
use tracing_subscriber::{EnvFilter, layer::SubscriberExt, util::SubscriberInitExt};

use crate::{Error, Settings};

const SENTRY_TRACES_SAMPLE_RATE: f32 = 0.1;
const SENTRY_SHUTDOWN_TIMEOUT: Duration = Duration::from_secs(2);

/// Initialize tracing subscribers for structured runtime logs.
pub fn init_tracing() {
    let env_filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("stockchartsalerts=info,info"));
    let _ = tracing_subscriber::registry()
        .with(env_filter)
        .with(tracing_subscriber::fmt::layer())
        .try_init();
}

/// Initialize Sentry when a DSN is configured.
#[must_use]
pub fn init_sentry(settings: &Settings) -> Option<ClientInitGuard> {
    sentry_options(settings).map(sentry::init)
}

/// Capture an application error in Sentry when Sentry is configured.
pub fn capture_error(error: &Error) {
    sentry::capture_error(error);
}

fn sentry_options(settings: &Settings) -> Option<ClientOptions> {
    Some(ClientOptions {
        dsn: Some(parse_dsn(&settings.sentry_dsn)?),
        environment: Some(settings.sentry_environment.clone().into()),
        release: settings.sentry_release().map(Into::into),
        traces_sample_rate: SENTRY_TRACES_SAMPLE_RATE,
        shutdown_timeout: SENTRY_SHUTDOWN_TIMEOUT,
        ..Default::default()
    })
}

fn parse_dsn(raw_dsn: &str) -> Option<Dsn> {
    let dsn = raw_dsn.trim();
    if dsn.is_empty() {
        return None;
    }

    match dsn.parse() {
        Ok(dsn) => Some(dsn),
        Err(error) => {
            warn!(%error, "invalid Sentry DSN, disabling Sentry");
            None
        }
    }
}

#[cfg(test)]
mod tests {
    use crate::Settings;

    use super::{SENTRY_SHUTDOWN_TIMEOUT, SENTRY_TRACES_SAMPLE_RATE, parse_dsn, sentry_options};

    fn settings(sentry_dsn: &str) -> Settings {
        Settings {
            minutes_between_runs: 5,
            discord_webhook_urls: vec!["https://discord.example/webhook".to_string()],
            sentry_dsn: sentry_dsn.to_string(),
            sentry_environment: "production".to_string(),
            git_commit: "abc123".to_string(),
            git_branch: "main".to_string(),
        }
    }

    #[test]
    fn parse_dsn_returns_none_for_missing_dsn() {
        assert!(parse_dsn("").is_none());
        assert!(parse_dsn("   ").is_none());
    }

    #[test]
    fn parse_dsn_returns_none_for_invalid_dsn() {
        assert!(parse_dsn("not a sentry dsn").is_none());
    }

    #[test]
    fn sentry_options_include_safe_metadata() {
        let options = sentry_options(&settings("https://public@example.com/1"))
            .expect("valid DSN should enable Sentry");

        assert!(options.dsn.is_some());
        assert_eq!(options.environment.as_deref(), Some("production"));
        assert_eq!(options.release.as_deref(), Some("main@abc123"));
        assert_eq!(options.traces_sample_rate, SENTRY_TRACES_SAMPLE_RATE);
        assert_eq!(options.shutdown_timeout, SENTRY_SHUTDOWN_TIMEOUT);
    }

    #[test]
    fn sentry_options_omit_unknown_release() {
        let mut settings = settings("https://public@example.com/1");
        settings.git_commit = "unknown".to_string();
        settings.git_branch = "unknown".to_string();

        let options = sentry_options(&settings).expect("valid DSN should enable Sentry");

        assert_eq!(options.release, None);
    }
}
