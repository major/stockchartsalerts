//! Binary entry point for StockCharts Alerts.

use std::process::ExitCode;

#[tokio::main]
async fn main() -> ExitCode {
    match stockchartsalerts::run().await {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}
