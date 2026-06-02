//! Shared HTTP client construction.

use std::time::Duration;

use reqwest::{Client, StatusCode};

use crate::{Error, Result};

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
        .map_err(Error::HttpClient)
}

/// Convert a non-success HTTP status into the shared service status error.
///
/// # Errors
///
/// Returns an error when the status is outside the HTTP success range.
pub fn ensure_success_status(service: &'static str, status: StatusCode) -> Result<()> {
    if status.is_success() {
        Ok(())
    } else {
        Err(Error::HttpStatus { service, status })
    }
}

#[cfg(test)]
mod tests {
    use reqwest::StatusCode;

    use crate::Error;

    #[test]
    fn success_statuses_are_accepted() {
        assert!(super::ensure_success_status("Example", StatusCode::OK).is_ok());
        assert!(super::ensure_success_status("Example", StatusCode::NO_CONTENT).is_ok());
    }

    #[test]
    fn failure_statuses_map_to_service_errors() {
        let error = super::ensure_success_status("Example", StatusCode::BAD_GATEWAY)
            .expect_err("non-success status should error");

        assert!(matches!(
            error,
            Error::HttpStatus {
                service: "Example",
                status: StatusCode::BAD_GATEWAY
            }
        ));
    }
}
