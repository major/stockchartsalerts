//! StockCharts alert fetching with retry behavior.

use std::time::Duration;

use reqwest::Client;
use serde_json::Value;
use tokio::time::sleep;
use tracing::{error, warn};

use crate::{Error, Result};

const DEFAULT_ALERTS_URL: &str = "https://stockcharts.com/j-sum/sum?cmd=alert";
const REFERER: &str = "https://stockcharts.com/freecharts/alertsummary.html";
const USER_AGENT: &str = "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0";

/// Client for fetching StockCharts alert payloads.
#[derive(Debug, Clone)]
pub struct StockChartsClient {
    http_client: Client,
    alerts_url: String,
    retry_delays: Vec<Duration>,
}

impl StockChartsClient {
    /// Build a StockCharts client around an existing HTTP client.
    #[must_use]
    pub fn with_http_client(http_client: Client) -> Self {
        Self {
            http_client,
            alerts_url: DEFAULT_ALERTS_URL.to_string(),
            retry_delays: vec![Duration::from_secs(2), Duration::from_secs(4)],
        }
    }

    /// Override the alert URL, primarily for tests.
    #[cfg(test)]
    #[must_use]
    pub fn with_alerts_url(mut self, alerts_url: impl Into<String>) -> Self {
        self.alerts_url = alerts_url.into();
        self
    }

    /// Override retry delays, primarily for tests.
    #[cfg(test)]
    #[must_use]
    pub fn with_retry_delays(mut self, retry_delays: Vec<Duration>) -> Self {
        self.retry_delays = retry_delays;
        self
    }

    /// Fetch alerts, returning an empty list after all retry attempts fail.
    pub async fn get_alerts(&self) -> Vec<Value> {
        match self.fetch_alerts().await {
            Ok(alerts) => alerts,
            Err(error) => {
                error!(%error, "failed to fetch alerts after all retries");
                Vec::new()
            }
        }
    }

    /// Fetch alerts with retry behavior.
    ///
    /// # Errors
    ///
    /// Returns an error if all attempts fail or the response payload is not a JSON array.
    pub async fn fetch_alerts(&self) -> Result<Vec<Value>> {
        let attempts = self.retry_delays.len() + 1;
        let mut last_error = None;

        for attempt in 1..=attempts {
            match self.fetch_alerts_once().await {
                Ok(alerts) => return Ok(alerts),
                Err(error) => {
                    if attempt == attempts {
                        return Err(error);
                    }

                    warn!(%error, attempt, attempts, "retrying StockCharts alert fetch");
                    last_error = Some(error);
                    sleep(self.retry_delays[attempt - 1]).await;
                }
            }
        }

        Err(last_error.unwrap_or_else(|| {
            Error::StockCharts("alert fetch failed without an error".to_string())
        }))
    }

    async fn fetch_alerts_once(&self) -> Result<Vec<Value>> {
        let response = self
            .http_client
            .get(&self.alerts_url)
            .header(reqwest::header::REFERER, REFERER)
            .header(reqwest::header::USER_AGENT, USER_AGENT)
            .send()
            .await
            .map_err(Error::HttpClient)?;

        let status = response.status();
        if !status.is_success() {
            return Err(Error::HttpStatus {
                service: "StockCharts",
                status,
            });
        }

        response
            .json::<Vec<Value>>()
            .await
            .map_err(Error::HttpClient)
    }
}

#[cfg(test)]
mod tests {
    use std::time::Duration;

    use mockito::Matcher;
    use reqwest::Client;
    use serde_json::json;

    use super::StockChartsClient;

    fn test_client(url: String) -> StockChartsClient {
        StockChartsClient::with_http_client(Client::new())
            .with_alerts_url(url)
            .with_retry_delays(vec![Duration::ZERO, Duration::ZERO])
    }

    #[tokio::test]
    async fn get_alerts_returns_stockcharts_payloads() {
        let mut server = mockito::Server::new_async().await;
        let mock = server
            .mock("GET", "/j-sum/sum")
            .match_query(Matcher::UrlEncoded("cmd".to_string(), "alert".to_string()))
            .match_header("referer", super::REFERER)
            .match_header("user-agent", super::USER_AGENT)
            .with_status(200)
            .with_body(
                json!([{ "alert": "Test", "lastfired": "31 Jul 2024, 12:33pm" }]).to_string(),
            )
            .create_async()
            .await;

        let alerts = test_client(format!("{}/j-sum/sum?cmd=alert", server.url()))
            .get_alerts()
            .await;

        mock.assert_async().await;
        assert_eq!(alerts.len(), 1);
        assert_eq!(alerts[0]["alert"], "Test");
    }

    #[tokio::test]
    async fn get_alerts_retries_then_returns_empty() {
        let mut server = mockito::Server::new_async().await;
        let mock = server
            .mock("GET", "/j-sum/sum")
            .match_query(Matcher::UrlEncoded("cmd".to_string(), "alert".to_string()))
            .with_status(500)
            .expect(3)
            .create_async()
            .await;

        let alerts = test_client(format!("{}/j-sum/sum?cmd=alert", server.url()))
            .get_alerts()
            .await;

        mock.assert_async().await;
        assert!(alerts.is_empty());
    }

    #[tokio::test]
    async fn get_alerts_succeeds_after_retry() {
        let mut server = mockito::Server::new_async().await;
        let failure = server
            .mock("GET", "/j-sum/sum")
            .match_query(Matcher::UrlEncoded("cmd".to_string(), "alert".to_string()))
            .with_status(500)
            .expect(1)
            .create_async()
            .await;
        let success = server
            .mock("GET", "/j-sum/sum")
            .match_query(Matcher::UrlEncoded("cmd".to_string(), "alert".to_string()))
            .with_status(200)
            .with_body(
                json!([{ "alert": "Recovered", "lastfired": "31 Jul 2024, 12:33pm" }]).to_string(),
            )
            .expect(1)
            .create_async()
            .await;

        let alerts = test_client(format!("{}/j-sum/sum?cmd=alert", server.url()))
            .get_alerts()
            .await;

        failure.assert_async().await;
        success.assert_async().await;
        assert_eq!(alerts[0]["alert"], "Recovered");
    }
}
