//! Error types for StockCharts Alerts.

use reqwest::StatusCode;

/// Convenient result alias for this crate.
pub type Result<T> = std::result::Result<T, Error>;

/// Errors produced by StockCharts Alerts.
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum Error {
    /// StockCharts alert payload was malformed.
    #[error("malformed StockCharts alert payload: {0}")]
    AlertPayload(String),
    /// Configuration was invalid.
    #[error("invalid configuration: {0}")]
    Config(String),
    /// HTTP client request or decode failed.
    #[error("HTTP client error: {0}")]
    HttpClient(#[from] reqwest::Error),
    /// HTTP service returned a non-success status code.
    #[error("{service} returned HTTP status {status}")]
    HttpStatus {
        /// Service that returned the status.
        service: &'static str,
        /// HTTP status code returned by the service.
        status: StatusCode,
    },
    /// StockCharts alert fetching failed.
    #[error("StockCharts error: {0}")]
    StockCharts(String),
    /// Shutdown signal handling failed.
    #[error("failed to wait for shutdown signal: {0}")]
    Signal(std::io::Error),
    /// StockCharts alert timestamp could not be parsed.
    #[error("failed to parse StockCharts timestamp: {0}")]
    TimeParse(String),
}
