//! Alert models, filtering, formatting, and StockCharts timestamp parsing.

use chrono::{DateTime, LocalResult, NaiveDateTime, TimeZone};
use chrono_tz::Tz;
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::Value;
use tracing::warn;

use crate::{Error, Result};

/// Time zone used by StockCharts alert timestamps.
pub const STOCKCHARTS_TIME_ZONE: Tz = chrono_tz::America::New_York;

const NO_ALERTS_PLACEHOLDER: &str = "There are no alerts today";

/// StockCharts alert payload fields used by the bot.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize, Serialize)]
pub struct Alert {
    /// Human-readable alert text.
    #[serde(deserialize_with = "deserialize_trimmed_string")]
    pub alert: String,
    /// Whether the alert is bearish. StockCharts uses the string "yes" for bearish alerts.
    #[serde(
        default = "default_bearish",
        deserialize_with = "deserialize_trimmed_string"
    )]
    pub bearish: String,
    /// Timestamp string from StockCharts.
    #[serde(deserialize_with = "deserialize_trimmed_string")]
    pub lastfired: String,
    /// Stock or index symbol. Missing values match the Python default.
    #[serde(
        default = "default_symbol",
        deserialize_with = "deserialize_trimmed_string"
    )]
    pub symbol: String,
}

impl Alert {
    /// Parse an alert from an arbitrary JSON value, ignoring unknown fields.
    ///
    /// # Errors
    ///
    /// Returns an error when required alert fields are missing or invalid.
    pub fn from_value(value: Value) -> Result<Self> {
        serde_json::from_value(value).map_err(|error| Error::AlertPayload(error.to_string()))
    }
}

/// Return alerts that are valid, not placeholder rows, and newer than `previous_run`.
#[must_use]
pub fn new_alerts_since(alerts: &[Value], previous_run: DateTime<Tz>) -> Vec<Alert> {
    let parsed_alerts = filter_alerts(alerts)
        .into_iter()
        .filter_map(|alert| match parse_stockcharts_time(&alert.lastfired) {
            Ok(fired_at) if fired_at > previous_run => Some((alert, fired_at)),
            Ok(_) => None,
            Err(error) => {
                warn!(symbol = %alert.symbol, %error, "failed to parse StockCharts alert timestamp");
                None
            }
        })
        .collect::<Vec<_>>();

    parsed_alerts
        .iter()
        .filter(|(alert, fired_at)| {
            parsed_alerts
                .iter()
                .filter(|(other, _)| other.symbol == alert.symbol)
                .all(|(_, other_fired_at)| other_fired_at <= fired_at)
        })
        .map(|(alert, _)| alert.clone())
        .collect()
}

/// Return valid, sendable alerts from StockCharts response payloads.
#[must_use]
pub fn filter_alerts(alerts: &[Value]) -> Vec<Alert> {
    alerts
        .iter()
        .filter_map(|value| match Alert::from_value(value.clone()) {
            Ok(alert) if alert.alert != NO_ALERTS_PLACEHOLDER => Some(alert),
            Ok(_) => None,
            Err(error) => {
                warn!(%error, "skipping malformed StockCharts alert payload");
                None
            }
        })
        .collect()
}

/// Parse a StockCharts timestamp in the America/New_York timezone.
///
/// # Errors
///
/// Returns an error when the timestamp format is unsupported or maps to no local time.
pub fn parse_stockcharts_time(value: &str) -> Result<DateTime<Tz>> {
    let cleaned = value.trim().trim_end_matches(" ET").trim();
    let naive = parse_naive_stockcharts_time(cleaned)?;

    match STOCKCHARTS_TIME_ZONE.from_local_datetime(&naive) {
        LocalResult::Single(datetime) => Ok(datetime),
        LocalResult::Ambiguous(earliest, _) => Ok(earliest),
        LocalResult::None => Err(Error::TimeParse(format!(
            "{value:?} is not a valid Eastern time"
        ))),
    }
}

fn parse_naive_stockcharts_time(value: &str) -> Result<NaiveDateTime> {
    const FORMATS: &[&str] = &["%e %b %Y, %-I:%M%P", "%e %b %Y, %-I:%M %p"];

    FORMATS
        .iter()
        .find_map(|format| NaiveDateTime::parse_from_str(value, format).ok())
        .ok_or_else(|| Error::TimeParse(format!("unsupported StockCharts timestamp {value:?}")))
}

fn default_bearish() -> String {
    "no".to_string()
}

fn default_symbol() -> String {
    "UNKNOWN".to_string()
}

fn deserialize_trimmed_string<'de, D>(deserializer: D) -> std::result::Result<String, D::Error>
where
    D: Deserializer<'de>,
{
    String::deserialize(deserializer).map(|value| value.trim().to_string())
}

#[cfg(test)]
mod tests {
    use chrono::TimeZone;
    use serde_json::json;

    use super::{
        Alert, STOCKCHARTS_TIME_ZONE, filter_alerts, new_alerts_since, parse_stockcharts_time,
    };

    fn sample_alerts() -> Vec<serde_json::Value> {
        vec![
            json!({
                "alert": "There are no alerts today",
                "newalert": "yes",
                "bearish": "",
                "lastfired": "1 Aug 2024, 8:11 AM ET"
            }),
            json!({
                "symbol": "$BPSPX",
                "alertpaused": "no",
                "bearish": "no",
                "notes": "",
                "alert": "S&P 500 Bullish Percent Index crosses above 70",
                "lastfired": "31 Jul 2024, 2:31pm",
                "newalert": "yes",
                "type": "a",
                "recid": "701"
            }),
            json!({
                "symbol": "$BPINFO",
                "alertpaused": "no",
                "bearish": "yes",
                "notes": "",
                "alert": "Technology Sector Bullish Percent Index crosses below 50",
                "lastfired": "31 Jul 2024, 12:55pm",
                "newalert": "yes",
                "type": "a",
                "recid": "1739"
            }),
            json!({
                "symbol": "$INDU",
                "alertpaused": "no",
                "bearish": "no",
                "notes": "",
                "alert": "Dow crosses above 41000",
                "lastfired": "31 Jul 2024, 12:33pm",
                "newalert": "yes",
                "type": "a",
                "recid": "452083"
            }),
            json!({
                "symbol": "$COMPQ",
                "alertpaused": "no",
                "bearish": "yes",
                "notes": "",
                "alert": "Nasdaq crosses below 17200",
                "lastfired": "31 Jul 2024, 11:47am",
                "newalert": "yes",
                "type": "a",
                "recid": "450121"
            }),
            json!({
                "symbol": "$COMPQ",
                "alertpaused": "no",
                "bearish": "yes",
                "notes": "",
                "alert": "Nasdaq crosses below 17300",
                "lastfired": "31 Jul 2024, 11:47am",
                "newalert": "yes",
                "type": "a",
                "recid": "450208"
            }),
        ]
    }

    #[test]
    fn alert_defaults_match_python_model() {
        let alert = Alert::from_value(json!({
            "alert": " Test alert ",
            "lastfired": " 31 Jul 2024, 12:33pm ",
            "ignored": "field"
        }))
        .expect("alert should deserialize");

        assert_eq!(alert.alert, "Test alert");
        assert_eq!(alert.lastfired, "31 Jul 2024, 12:33pm");
        assert_eq!(alert.bearish, "no");
        assert_eq!(alert.symbol, "UNKNOWN");
    }

    #[test]
    fn filter_alerts_skips_placeholder_and_malformed_rows() {
        let mut alerts = sample_alerts();
        alerts.push(json!({"alert": "missing lastfired"}));

        let filtered = filter_alerts(&alerts);

        assert_eq!(filtered.len(), 5);
        assert_eq!(filtered[0].symbol, "$BPSPX");
    }

    #[test]
    fn new_alerts_since_matches_existing_python_filter() {
        let previous_run = STOCKCHARTS_TIME_ZONE
            .with_ymd_and_hms(2024, 7, 31, 12, 0, 0)
            .single()
            .expect("valid timestamp");

        let alerts = new_alerts_since(&sample_alerts(), previous_run);

        assert_eq!(alerts.len(), 3);
        assert_eq!(
            alerts
                .iter()
                .map(|alert| alert.symbol.as_str())
                .collect::<Vec<_>>(),
            vec!["$BPSPX", "$BPINFO", "$INDU"]
        );
    }

    #[test]
    fn new_alerts_since_keeps_latest_alerts_per_symbol() {
        let previous_run = STOCKCHARTS_TIME_ZONE
            .with_ymd_and_hms(2026, 6, 8, 9, 29, 0)
            .single()
            .expect("valid timestamp");
        let alerts = vec![
            json!({
                "symbol": "$COMPQ",
                "bearish": "yes",
                "alert": "Nasdaq crosses below 25800",
                "lastfired": "8 Jun 2026, 9:30am"
            }),
            json!({
                "symbol": "$COMPQ",
                "bearish": "no",
                "alert": "Nasdaq crosses above 25800",
                "lastfired": "8 Jun 2026, 9:33am"
            }),
            json!({
                "symbol": "$COMPQ",
                "bearish": "no",
                "alert": "Nasdaq crosses above 25900",
                "lastfired": "8 Jun 2026, 9:33am"
            }),
            json!({
                "symbol": "$GOLD",
                "bearish": "yes",
                "alert": "Gold crosses below 4400",
                "lastfired": "8 Jun 2026, 9:30am"
            }),
        ];

        let alerts = new_alerts_since(&alerts, previous_run);

        assert_eq!(alerts.len(), 3);
        assert_eq!(
            alerts
                .iter()
                .map(|alert| alert.alert.as_str())
                .collect::<Vec<_>>(),
            vec![
                "Nasdaq crosses above 25800",
                "Nasdaq crosses above 25900",
                "Gold crosses below 4400"
            ]
        );
    }

    #[test]
    fn parse_stockcharts_time_uses_eastern_time() {
        let parsed = parse_stockcharts_time("31 Jul 2024, 2:31pm").expect("timestamp should parse");

        assert_eq!(parsed.timezone(), STOCKCHARTS_TIME_ZONE);
        assert_eq!(parsed.to_rfc3339(), "2024-07-31T14:31:00-04:00");
    }

    #[test]
    fn parse_stockcharts_time_accepts_uppercase_am_pm_and_et_suffix() {
        let parsed =
            parse_stockcharts_time("1 Aug 2024, 8:11 AM ET").expect("timestamp should parse");

        assert_eq!(parsed.to_rfc3339(), "2024-08-01T08:11:00-04:00");
    }

    #[test]
    fn parse_stockcharts_time_handles_dst_fall_ambiguity_deterministically() {
        let parsed =
            parse_stockcharts_time("3 Nov 2024, 1:30am").expect("ambiguous timestamp should parse");

        assert_eq!(parsed.to_rfc3339(), "2024-11-03T01:30:00-04:00");
    }
}
