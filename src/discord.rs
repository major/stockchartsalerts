//! Discord webhook payload formatting and delivery.

use reqwest::Client;
use serde::Serialize;
use tracing::{error, info};

use crate::{
    Result,
    alerts::{Alert, emoji_for_alert, format_discord_alert_text},
    http::build_http_client,
};

const AVATAR_URL: &str = "https://emojiguide.org/images/emoji/1/8z8e40kucdd1.png";

/// Client for sending Discord webhook messages.
#[derive(Debug, Clone)]
pub struct DiscordClient {
    http_client: Client,
}

impl DiscordClient {
    /// Build a Discord client that uses the shared persistent HTTP client.
    ///
    /// # Errors
    ///
    /// Returns an error when the HTTP client cannot be constructed.
    pub fn new() -> Result<Self> {
        Ok(Self::with_http_client(build_http_client()?))
    }

    /// Build a Discord client around an existing HTTP client.
    #[must_use]
    pub fn with_http_client(http_client: Client) -> Self {
        Self { http_client }
    }

    /// Send an alert to all configured Discord webhooks, logging and continuing on failures.
    pub async fn send_alert_to_webhooks(&self, alert: &Alert, webhook_urls: &[String]) {
        info!(alert = %alert.alert, lastfired = %alert.lastfired, "sending alert to Discord");

        for (index, webhook_url) in webhook_urls.iter().enumerate() {
            let payload = DiscordWebhookPayload::from_alert(alert);
            match self.send_payload(webhook_url, &payload).await {
                Ok(()) => {
                    info!(webhook = index + 1, total = webhook_urls.len(), symbol = %alert.symbol, "alert sent to Discord")
                }
                Err(error) => {
                    error!(webhook = index + 1, total = webhook_urls.len(), symbol = %alert.symbol, %error, "Discord webhook failed")
                }
            }
        }
    }

    async fn send_payload(&self, webhook_url: &str, payload: &DiscordWebhookPayload) -> Result<()> {
        let response = self
            .http_client
            .post(webhook_url)
            .json(payload)
            .send()
            .await
            .map_err(crate::Error::HttpClient)?;
        let status = response.status();

        if status.is_success() {
            Ok(())
        } else {
            Err(crate::Error::HttpStatus {
                service: "Discord",
                status,
            })
        }
    }
}

/// JSON payload sent to Discord webhooks.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct DiscordWebhookPayload {
    /// Username displayed for the webhook message.
    pub username: String,
    /// Avatar URL displayed for the webhook message.
    pub avatar_url: &'static str,
    /// Message content.
    pub content: String,
}

impl DiscordWebhookPayload {
    /// Build the Discord payload for an alert.
    #[must_use]
    pub fn from_alert(alert: &Alert) -> Self {
        Self {
            username: alert.symbol.clone(),
            avatar_url: AVATAR_URL,
            content: format!(
                "{}  {}",
                emoji_for_alert(alert),
                format_discord_alert_text(&alert.alert)
            ),
        }
    }
}

#[cfg(test)]
mod tests {
    use mockito::Matcher;
    use reqwest::Client;
    use serde_json::json;

    use crate::alerts::Alert;

    use super::{DiscordClient, DiscordWebhookPayload};

    fn alert(text: &str, bearish: &str, symbol: &str) -> Alert {
        Alert::from_value(json!({
            "alert": text,
            "bearish": bearish,
            "lastfired": "31 Jul 2024, 12:33pm",
            "symbol": symbol
        }))
        .expect("valid alert")
    }

    #[test]
    fn payload_matches_python_discord_format() {
        let payload = DiscordWebhookPayload::from_alert(&alert("Test alert", "no", "$COMPQ"));

        assert_eq!(payload.username, "$COMPQ");
        assert_eq!(payload.avatar_url, super::AVATAR_URL);
        assert_eq!(payload.content, "💚  Test alert");
    }

    #[test]
    fn payload_rewrites_dow_crosses_above() {
        let payload =
            DiscordWebhookPayload::from_alert(&alert("Dow crosses above 41000", "no", "$INDU"));

        assert_eq!(payload.content, "💚  THE DOW, THE DOW IS ABOVE 41000");
    }

    #[tokio::test]
    async fn sends_alert_to_multiple_webhooks() {
        let mut server = mockito::Server::new_async().await;
        let first = server
            .mock("POST", "/webhooks/1/abc")
            .match_body(Matcher::Json(json!({
                "username": "$COMPQ",
                "avatar_url": super::AVATAR_URL,
                "content": "💚  Test alert"
            })))
            .with_status(204)
            .expect(1)
            .create_async()
            .await;
        let second = server
            .mock("POST", "/webhooks/2/def")
            .match_body(Matcher::Json(json!({
                "username": "$COMPQ",
                "avatar_url": super::AVATAR_URL,
                "content": "💚  Test alert"
            })))
            .with_status(204)
            .expect(1)
            .create_async()
            .await;

        let webhook_urls = vec![
            format!("{}/webhooks/1/abc", server.url()),
            format!("{}/webhooks/2/def", server.url()),
        ];
        DiscordClient::with_http_client(Client::new())
            .send_alert_to_webhooks(&alert("Test alert", "no", "$COMPQ"), &webhook_urls)
            .await;

        first.assert_async().await;
        second.assert_async().await;
    }

    #[tokio::test]
    async fn discord_error_status_does_not_stop_later_webhooks() {
        let mut server = mockito::Server::new_async().await;
        let first = server
            .mock("POST", "/webhooks/1/abc")
            .with_status(400)
            .expect(1)
            .create_async()
            .await;
        let second = server
            .mock("POST", "/webhooks/2/def")
            .with_status(204)
            .expect(1)
            .create_async()
            .await;

        let webhook_urls = vec![
            format!("{}/webhooks/1/abc", server.url()),
            format!("{}/webhooks/2/def", server.url()),
        ];
        DiscordClient::with_http_client(Client::new())
            .send_alert_to_webhooks(&alert("Test alert", "no", "$COMPQ"), &webhook_urls)
            .await;

        first.assert_async().await;
        second.assert_async().await;
    }
}
