//! StockCharts alert polling and Discord delivery.

#![deny(missing_docs)]

/// Alert models, filtering, formatting, and timestamp parsing.
pub mod alerts;
/// Application configuration.
pub mod config;
/// Application error types.
pub mod error;

pub use config::{Cli, Settings};
pub use error::{Error, Result};

/// Run the application until shutdown.
///
/// # Errors
///
/// Returns an error when configuration is invalid or the runtime cannot initialize.
pub async fn run() -> Result<()> {
    let _settings = Settings::from_cli(Cli::parse())?;
    Ok(())
}
