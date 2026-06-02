//! Application orchestration for fetching and delivering alerts.

use chrono::{DateTime, Duration, Utc};
use chrono_tz::Tz;
use tokio::time::{Duration as TokioDuration, MissedTickBehavior, interval, sleep};
use tracing::{error, info, warn};

use crate::{
    Result, Settings,
    alerts::{STOCKCHARTS_TIME_ZONE, new_alerts_since},
    discord::DiscordClient,
    http::build_http_client,
    stockcharts::StockChartsClient,
    telemetry::{init_sentry, init_tracing},
};

const MAX_CONSECUTIVE_ERRORS: u64 = 5;
const NORMAL_ERROR_BACKOFF: TokioDuration = TokioDuration::from_secs(60);
const EXTENDED_ERROR_BACKOFF: TokioDuration = TokioDuration::from_secs(300);

/// Runtime application state.
#[derive(Debug, Clone)]
pub struct App {
    settings: Settings,
    stockcharts_client: StockChartsClient,
    discord_client: DiscordClient,
}

impl App {
    /// Build the application with one shared persistent HTTP client.
    ///
    /// # Errors
    ///
    /// Returns an error when the shared HTTP client cannot be constructed.
    pub fn new(settings: Settings) -> Result<Self> {
        let http_client = build_http_client()?;
        Ok(Self::with_clients(
            settings,
            StockChartsClient::with_http_client(http_client.clone()),
            DiscordClient::with_http_client(http_client),
        ))
    }

    /// Build the application from explicit clients, primarily for tests.
    #[must_use]
    pub fn with_clients(
        settings: Settings,
        stockcharts_client: StockChartsClient,
        discord_client: DiscordClient,
    ) -> Self {
        Self {
            settings,
            stockcharts_client,
            discord_client,
        }
    }

    /// Fetch and send alerts using the current time.
    pub async fn send_alerts_once(&self) -> Result<usize> {
        self.send_alerts_once_at(Utc::now().with_timezone(&STOCKCHARTS_TIME_ZONE))
            .await
    }

    /// Fetch and send alerts using a supplied current time, primarily for tests.
    pub async fn send_alerts_once_at(&self, now: DateTime<Tz>) -> Result<usize> {
        let alerts = self.stockcharts_client.get_alerts().await;
        let previous_run = now - Duration::minutes(i64::from(self.settings.minutes_between_runs));
        let new_alerts = new_alerts_since(&alerts, previous_run);

        for alert in &new_alerts {
            self.discord_client
                .send_alert_to_webhooks(alert, &self.settings.discord_webhook_urls)
                .await;
        }

        Ok(new_alerts.len())
    }

    /// Run the initial check and interval scheduler until Ctrl-C is received.
    ///
    /// # Errors
    ///
    /// Returns an error if waiting for the shutdown signal fails.
    pub async fn run_until_shutdown(&self) -> Result<()> {
        info!("running initial alert check");
        if let Err(error) = self.send_alerts_once().await {
            error!(%error, "error during initial alert check");
        }

        let mut ticker = interval(TokioDuration::from_secs(
            u64::from(self.settings.minutes_between_runs) * 60,
        ));
        ticker.set_missed_tick_behavior(MissedTickBehavior::Delay);
        ticker.tick().await;

        let mut consecutive_errors = 0_u64;

        loop {
            tokio::select! {
                biased;

                signal = tokio::signal::ctrl_c() => {
                    signal.map_err(crate::Error::Signal)?;
                    info!("shutting down gracefully");
                    return Ok(());
                }
                _ = ticker.tick() => {
                    match self.send_alerts_once().await {
                        Ok(sent) => {
                            consecutive_errors = 0;
                            info!(sent, "alert check completed");
                        }
                        Err(error) => {
                            consecutive_errors += 1;
                            error!(%error, consecutive_errors, "error in scheduler loop");
                            let delay = scheduler_error_backoff(consecutive_errors);
                            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS {
                                warn!(consecutive_errors, seconds = delay.as_secs(), "too many consecutive errors, backing off");
                            }
                            sleep(delay).await;
                        }
                    }
                }
            }
        }
    }
}

/// Run the full application from CLI/environment settings.
///
/// # Errors
///
/// Returns an error when configuration or runtime initialization fails.
pub async fn run(settings: Settings) -> Result<()> {
    init_tracing();
    settings.log_safe();
    let _sentry_guard = init_sentry(&settings);
    info!(version = %settings.release(), "running StockCharts Alerts Bot");
    App::new(settings)?.run_until_shutdown().await
}

fn scheduler_error_backoff(consecutive_errors: u64) -> TokioDuration {
    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS {
        EXTENDED_ERROR_BACKOFF
    } else {
        NORMAL_ERROR_BACKOFF
    }
}

#[cfg(test)]
mod tests {
    use std::time::Duration as StdDuration;

    use chrono::TimeZone;
    use mockito::Matcher;
    use reqwest::Client;
    use serde_json::json;

    use crate::{
        Settings, alerts::STOCKCHARTS_TIME_ZONE, discord::DiscordClient,
        stockcharts::StockChartsClient,
    };

    use super::{App, EXTENDED_ERROR_BACKOFF, NORMAL_ERROR_BACKOFF, scheduler_error_backoff};

    fn settings(webhook_url: String) -> Settings {
        Settings {
            minutes_between_runs: 5,
            discord_webhook_urls: vec![webhook_url],
            sentry_dsn: String::new(),
            sentry_environment: "production".to_string(),
            git_commit: "abc123".to_string(),
            git_branch: "main".to_string(),
        }
    }

    #[tokio::test]
    async fn send_alerts_once_fetches_filters_and_posts_new_alerts() {
        let mut server = mockito::Server::new_async().await;
        let stockcharts = server
            .mock("GET", "/j-sum/sum")
            .match_query(Matcher::UrlEncoded("cmd".to_string(), "alert".to_string()))
            .with_status(200)
            .with_body(
                json!([
                    {"alert": "There are no alerts today", "lastfired": "31 Jul 2024, 2:31pm"},
                    {"symbol": "$BPSPX", "alert": "S&P 500 Bullish Percent Index crosses above 70", "bearish": "no", "lastfired": "31 Jul 2024, 2:31pm"},
                    {"symbol": "$COMPQ", "alert": "Nasdaq crosses below 17200", "bearish": "yes", "lastfired": "31 Jul 2024, 11:47am"}
                ])
                .to_string(),
            )
            .expect(1)
            .create_async()
            .await;
        let discord = server
            .mock("POST", "/webhooks/1/abc")
            .match_body(Matcher::Json(json!({
                "username": "$BPSPX",
                "avatar_url": "https://emojiguide.org/images/emoji/1/8z8e40kucdd1.png",
                "content": "💚  S&P 500 Bullish Percent Index crosses above 70"
            })))
            .with_status(204)
            .expect(1)
            .create_async()
            .await;

        let http_client = Client::new();
        let app = App::with_clients(
            settings(format!("{}/webhooks/1/abc", server.url())),
            StockChartsClient::with_http_client(http_client.clone())
                .with_alerts_url(format!("{}/j-sum/sum?cmd=alert", server.url()))
                .with_retry_delays(vec![StdDuration::ZERO, StdDuration::ZERO]),
            DiscordClient::with_http_client(http_client),
        );
        let now = STOCKCHARTS_TIME_ZONE
            .with_ymd_and_hms(2024, 7, 31, 12, 0, 0)
            .single()
            .expect("valid timestamp");

        let sent = app
            .send_alerts_once_at(now)
            .await
            .expect("send should succeed");

        stockcharts.assert_async().await;
        discord.assert_async().await;
        assert_eq!(sent, 1);
    }

    #[test]
    fn scheduler_error_backoff_matches_python_threshold() {
        assert_eq!(scheduler_error_backoff(1), NORMAL_ERROR_BACKOFF);
        assert_eq!(scheduler_error_backoff(4), NORMAL_ERROR_BACKOFF);
        assert_eq!(scheduler_error_backoff(5), EXTENDED_ERROR_BACKOFF);
    }
}
