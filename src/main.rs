//! Binary entry point for StockCharts Alerts.

use std::process::ExitCode;

fn main() -> ExitCode {
    match stockchartsalerts::run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}
