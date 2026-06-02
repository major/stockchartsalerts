//! Error types for StockCharts Alerts.

/// Convenient result alias for this crate.
pub type Result<T> = std::result::Result<T, Error>;

/// Errors produced by StockCharts Alerts.
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum Error {
    /// Configuration was invalid.
    #[error("invalid configuration: {0}")]
    Config(String),
}
