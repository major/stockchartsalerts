//! Logging and Sentry initialization.

use sentry::ClientInitGuard;
use tracing_subscriber::{EnvFilter, layer::SubscriberExt, util::SubscriberInitExt};

use crate::Settings;

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
    if settings.sentry_dsn.is_empty() {
        return None;
    }

    Some(sentry::init((
        settings.sentry_dsn.clone(),
        sentry::ClientOptions {
            environment: Some(settings.sentry_environment.clone().into()),
            release: Some(settings.release().into()),
            traces_sample_rate: 0.1,
            ..Default::default()
        },
    )))
}

#[cfg(test)]
mod tests {
    use crate::Settings;

    fn settings(sentry_dsn: &str) -> Settings {
        Settings {
            minutes_between_runs: 5,
            discord_webhook_urls: vec!["https://discord.example/webhook".to_string()],
            sentry_dsn: sentry_dsn.to_string(),
            sentry_environment: "test".to_string(),
            git_commit: "abc123".to_string(),
            git_branch: "main".to_string(),
        }
    }

    #[test]
    fn tracing_initialization_is_idempotent() {
        super::init_tracing();
        super::init_tracing();
    }

    #[test]
    fn sentry_initialization_skips_empty_dsn() {
        assert!(super::init_sentry(&settings("")).is_none());
    }

    #[test]
    fn sentry_initialization_returns_guard_when_configured() {
        let guard = super::init_sentry(&settings("https://public@example.com/1"));

        assert!(guard.is_some());
    }
}
