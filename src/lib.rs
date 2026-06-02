//! StockCharts alert polling and Discord delivery.

#![deny(missing_docs)]

mod alerts;
mod app;
mod config;
mod discord;
mod error;
mod http;
mod stockcharts;
mod telemetry;

pub use error::{Error, Result};

use config::{Cli, Settings};

/// Run the application until shutdown.
///
/// # Errors
///
/// Returns an error when configuration is invalid or the runtime cannot initialize.
pub async fn run() -> Result<()> {
    app::run(Settings::from_cli(Cli::parse())?).await
}
