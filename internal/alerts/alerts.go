// Package alerts provides alert models, filtering, and StockCharts timestamp parsing.
package alerts

import (
	"encoding/json"
	"log/slog"
	"strings"
	"time"
	// Blank-imported to embed the IANA timezone database in the binary,
	// so timezone lookups work even without system tzdata (e.g. in minimal container images).
	_ "time/tzdata"

	"github.com/major/stockchartsalerts/internal/xerrors"
)

// Alert represents a StockCharts alert payload.
type Alert struct {
	// Alert is the human-readable alert text.
	Alert string
	// Bearish indicates whether the alert is bearish ("yes" or "no").
	Bearish string
	// LastFired is the timestamp string from StockCharts.
	LastFired string
	// Symbol is the stock or index symbol.
	Symbol string
}

const (
	// NoAlertsPlaceholder is the placeholder text for days with no alerts.
	NoAlertsPlaceholder = "There are no alerts today"
	// StockChartsTimeZoneName is the IANA timezone name used by StockCharts.
	StockChartsTimeZoneName = "America/New_York"
)

// stockChartsTimeZone is the cached America/New_York timezone.
// Initialized once at package init time.
var stockChartsTimeZone *time.Location

func init() {
	var err error
	stockChartsTimeZone, err = time.LoadLocation(StockChartsTimeZoneName)
	if err != nil {
		// This should never happen with the embedded tzdata, but fail loudly if it does.
		panic("failed to load America/New_York timezone: " + err.Error())
	}
}

// StockChartsTimeZone returns the cached America/New_York timezone.
// This timezone is loaded once at package initialization and is guaranteed to be valid.
func StockChartsTimeZone() *time.Location {
	return stockChartsTimeZone
}

// UnmarshalJSON unmarshals an Alert from JSON, applying field defaults (Bearish
// defaults to "no", Symbol defaults to "UNKNOWN" when absent) and trimming
// surrounding whitespace from every string field.
func (a *Alert) UnmarshalJSON(data []byte) error {
	// Use a raw struct with pointer fields to detect missing values.
	type rawAlert struct {
		Alert     *string `json:"alert"`
		Bearish   *string `json:"bearish"`
		LastFired *string `json:"lastfired"`
		Symbol    *string `json:"symbol"`
	}

	var raw rawAlert
	if err := json.Unmarshal(data, &raw); err != nil {
		return err
	}

	// Apply defaults and trim all fields.
	a.Alert = trimString(raw.Alert, "")
	a.Bearish = trimString(raw.Bearish, "no")
	a.LastFired = trimString(raw.LastFired, "")
	a.Symbol = trimString(raw.Symbol, "UNKNOWN")

	return nil
}

// trimString returns the trimmed value if non-nil and non-empty, otherwise the default.
func trimString(value *string, defaultValue string) string {
	if value == nil {
		return defaultValue
	}
	trimmed := strings.TrimSpace(*value)
	if trimmed == "" {
		return defaultValue
	}
	return trimmed
}

// FilterAlerts returns valid, sendable alerts from StockCharts response payloads.
// It drops the "There are no alerts today" placeholder rows and malformed/unparseable rows,
// logging and skipping rather than erroring.
func FilterAlerts(alerts []json.RawMessage) []Alert {
	var result []Alert
	for _, rawMsg := range alerts {
		var alert Alert
		if err := json.Unmarshal(rawMsg, &alert); err != nil {
			slog.Warn("skipping malformed StockCharts alert payload", "error", err)
			continue
		}
		if alert.Alert == NoAlertsPlaceholder {
			continue
		}
		result = append(result, alert)
	}
	return result
}

// NewAlertsSince returns alerts that are valid, not placeholder rows, and newer than previousRun.
// For alerts sharing the same symbol, it keeps only the one(s) at the latest fired-at timestamp
// (ties are kept).
func NewAlertsSince(alerts []json.RawMessage, previousRun time.Time) []Alert {
	filtered := FilterAlerts(alerts)

	// Parse timestamps and filter by previousRun.
	type alertWithTime struct {
		alert   Alert
		firedAt time.Time
	}
	var parsed []alertWithTime
	for _, alert := range filtered {
		firedAt, err := ParseStockChartsTime(alert.LastFired)
		if err != nil {
			slog.Warn("failed to parse StockCharts alert timestamp", "symbol", alert.Symbol, "error", err)
			continue
		}
		if firedAt.After(previousRun) {
			parsed = append(parsed, alertWithTime{alert, firedAt})
		}
	}

	// Keep only the latest-fired alert(s) per symbol.
	var result []Alert
	for _, candidate := range parsed {
		isLatest := true
		for _, other := range parsed {
			if other.alert.Symbol == candidate.alert.Symbol && other.firedAt.After(candidate.firedAt) {
				isLatest = false
				break
			}
		}
		if isLatest {
			result = append(result, candidate.alert)
		}
	}

	return result
}

// ParseStockChartsTime parses a StockCharts timestamp in the America/New_York timezone.
// It strips trailing " ET" (case-sensitive), then parses against known formats.
// For DST fall-back ambiguity, it picks the earliest instant.
func ParseStockChartsTime(value string) (time.Time, error) {
	// Strip trailing " ET" and trim.
	cleaned := strings.TrimSpace(value)
	cleaned = strings.TrimSuffix(cleaned, " ET")
	cleaned = strings.TrimSpace(cleaned)

	// Try all known formats.
	// StockCharts uses two formats:
	// 1. "31 Jul 2024, 2:31pm" (lowercase am/pm, no space)
	// 2. "1 Aug 2024, 8:11 AM" (uppercase AM/PM, with space)
	// Go's time.Parse is case-sensitive for AM/PM, so we need both variants.
	formats := []string{
		"2 Jan 2006, 3:04pm",  // lowercase am/pm, no space
		"2 Jan 2006, 3:04 PM", // uppercase AM/PM, with space
	}

	var parsedTime time.Time
	for _, format := range formats {
		t, err := time.ParseInLocation(format, cleaned, stockChartsTimeZone)
		if err == nil {
			parsedTime = t
			return parsedTime, nil
		}
	}

	// If no format matched, return an error.
	return time.Time{}, xerrors.TimeParse("unsupported StockCharts timestamp: " + value)
}
