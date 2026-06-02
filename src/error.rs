//! Error types for StockCharts Alerts.

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
    /// StockCharts alert timestamp could not be parsed.
    #[error("failed to parse StockCharts timestamp: {0}")]
    TimeParse(String),
}
