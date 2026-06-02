//! Shared HTTP client construction.

use std::time::Duration;

use reqwest::Client;

use crate::Result;

/// StockCharts and Discord HTTP timeout.
pub const HTTP_TIMEOUT: Duration = Duration::from_secs(30);

/// Build the single persistent HTTP client used by the application.
///
/// # Errors
///
/// Returns an error when the client cannot be constructed.
pub fn build_http_client() -> Result<Client> {
    Client::builder()
        .timeout(HTTP_TIMEOUT)
        .pool_max_idle_per_host(5)
        .pool_idle_timeout(Duration::from_secs(30))
        .redirect(reqwest::redirect::Policy::limited(10))
        .build()
        .map_err(crate::Error::HttpClient)
}
