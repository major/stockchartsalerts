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
