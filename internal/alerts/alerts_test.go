package alerts

import (
	"encoding/json"
	"testing"
	"time"
)

func TestAlertDefaults(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected Alert
	}{
		{
			name: "all_fields_present",
			input: `{
				"alert": " Test alert ",
				"bearish": "yes",
				"lastfired": " 31 Jul 2024, 12:33pm ",
				"symbol": " $COMPQ "
			}`,
			expected: Alert{
				Alert:     "Test alert",
				Bearish:   "yes",
				LastFired: "31 Jul 2024, 12:33pm",
				Symbol:    "$COMPQ",
			},
		},
		{
			name: "missing_bearish_defaults_to_no",
			input: `{
				"alert": "Test alert",
				"lastfired": "31 Jul 2024, 12:33pm"
			}`,
			expected: Alert{
				Alert:     "Test alert",
				Bearish:   "no",
				LastFired: "31 Jul 2024, 12:33pm",
				Symbol:    "UNKNOWN",
			},
		},
		{
			name: "missing_symbol_defaults_to_unknown",
			input: `{
				"alert": "Test alert",
				"bearish": "no",
				"lastfired": "31 Jul 2024, 12:33pm"
			}`,
			expected: Alert{
				Alert:     "Test alert",
				Bearish:   "no",
				LastFired: "31 Jul 2024, 12:33pm",
				Symbol:    "UNKNOWN",
			},
		},
		{
			name: "empty_bearish_defaults_to_no",
			input: `{
				"alert": "Test alert",
				"bearish": "",
				"lastfired": "31 Jul 2024, 12:33pm",
				"symbol": "$COMPQ"
			}`,
			expected: Alert{
				Alert:     "Test alert",
				Bearish:   "no",
				LastFired: "31 Jul 2024, 12:33pm",
				Symbol:    "$COMPQ",
			},
		},
		{
			name: "whitespace_only_fields_use_defaults",
			input: `{
				"alert": "Test alert",
				"bearish": "   ",
				"lastfired": "31 Jul 2024, 12:33pm",
				"symbol": "  "
			}`,
			expected: Alert{
				Alert:     "Test alert",
				Bearish:   "no",
				LastFired: "31 Jul 2024, 12:33pm",
				Symbol:    "UNKNOWN",
			},
		},
		{
			name: "ignores_unknown_fields",
			input: `{
				"alert": "Test alert",
				"lastfired": "31 Jul 2024, 12:33pm",
				"ignored": "field",
				"newalert": "yes"
			}`,
			expected: Alert{
				Alert:     "Test alert",
				Bearish:   "no",
				LastFired: "31 Jul 2024, 12:33pm",
				Symbol:    "UNKNOWN",
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var alert Alert
			if err := json.Unmarshal([]byte(tt.input), &alert); err != nil {
				t.Fatalf("unmarshal failed: %v", err)
			}
			if alert != tt.expected {
				t.Errorf("got %+v, want %+v", alert, tt.expected)
			}
		})
	}
}

func TestFilterAlerts(t *testing.T) {
	tests := []struct {
		name     string
		input    []string
		expected int
		symbols  []string
	}{
		{
			name: "skips_placeholder_row",
			input: []string{
				`{"alert": "There are no alerts today", "lastfired": "1 Aug 2024, 8:11 AM"}`,
				`{"alert": "Test alert", "lastfired": "31 Jul 2024, 2:31pm", "symbol": "$BPSPX"}`,
			},
			expected: 1,
			symbols:  []string{"$BPSPX"},
		},
		{
			name: "skips_placeholder_and_malformed",
			input: []string{
				`{"alert": "There are no alerts today", "lastfired": "1 Aug 2024, 8:11 AM"}`,
				`{invalid json}`,
				`{"alert": "Test alert", "lastfired": "31 Jul 2024, 2:31pm", "symbol": "$BPSPX"}`,
			},
			expected: 1,
			symbols:  []string{"$BPSPX"},
		},
		{
			name: "keeps_valid_alerts",
			input: []string{
				`{"alert": "Alert 1", "lastfired": "31 Jul 2024, 2:31pm", "symbol": "$A"}`,
				`{"alert": "Alert 2", "lastfired": "31 Jul 2024, 12:55pm", "symbol": "$B"}`,
				`{"alert": "Alert 3", "lastfired": "31 Jul 2024, 12:33pm", "symbol": "$C"}`,
			},
			expected: 3,
			symbols:  []string{"$A", "$B", "$C"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var rawMsgs []json.RawMessage
			for _, s := range tt.input {
				rawMsgs = append(rawMsgs, json.RawMessage(s))
			}

			result := FilterAlerts(rawMsgs)
			if len(result) != tt.expected {
				t.Errorf("got %d alerts, want %d", len(result), tt.expected)
			}

			for i, alert := range result {
				if i < len(tt.symbols) && alert.Symbol != tt.symbols[i] {
					t.Errorf("alert %d: got symbol %q, want %q", i, alert.Symbol, tt.symbols[i])
				}
			}
		})
	}
}

func sampleAlerts() []json.RawMessage {
	return []json.RawMessage{
		json.RawMessage(`{
			"alert": "There are no alerts today",
			"newalert": "yes",
			"bearish": "",
			"lastfired": "1 Aug 2024, 8:11 AM ET"
		}`),
		json.RawMessage(`{
			"symbol": "$BPSPX",
			"alertpaused": "no",
			"bearish": "no",
			"notes": "",
			"alert": "S&P 500 Bullish Percent Index crosses above 70",
			"lastfired": "31 Jul 2024, 2:31pm",
			"newalert": "yes",
			"type": "a",
			"recid": "701"
		}`),
		json.RawMessage(`{
			"symbol": "$BPINFO",
			"alertpaused": "no",
			"bearish": "yes",
			"notes": "",
			"alert": "Technology Sector Bullish Percent Index crosses below 50",
			"lastfired": "31 Jul 2024, 12:55pm",
			"newalert": "yes",
			"type": "a",
			"recid": "1739"
		}`),
		json.RawMessage(`{
			"symbol": "$INDU",
			"alertpaused": "no",
			"bearish": "no",
			"notes": "",
			"alert": "Dow crosses above 41000",
			"lastfired": "31 Jul 2024, 12:33pm",
			"newalert": "yes",
			"type": "a",
			"recid": "452083"
		}`),
		json.RawMessage(`{
			"symbol": "$COMPQ",
			"alertpaused": "no",
			"bearish": "yes",
			"notes": "",
			"alert": "Nasdaq crosses below 17200",
			"lastfired": "31 Jul 2024, 11:47am",
			"newalert": "yes",
			"type": "a",
			"recid": "450121"
		}`),
		json.RawMessage(`{
			"symbol": "$COMPQ",
			"alertpaused": "no",
			"bearish": "yes",
			"notes": "",
			"alert": "Nasdaq crosses below 17300",
			"lastfired": "31 Jul 2024, 11:47am",
			"newalert": "yes",
			"type": "a",
			"recid": "450208"
		}`),
	}
}

func TestNewAlertsSinceMatchesPythonFilter(t *testing.T) {
	// Previous run at 2024-07-31 12:00:00 EDT
	previousRun := time.Date(2024, 7, 31, 12, 0, 0, 0, stockChartsTimeZone)

	alerts := NewAlertsSince(sampleAlerts(), previousRun)

	if len(alerts) != 3 {
		t.Errorf("got %d alerts, want 3", len(alerts))
	}

	expectedSymbols := []string{"$BPSPX", "$BPINFO", "$INDU"}
	for i, alert := range alerts {
		if i < len(expectedSymbols) && alert.Symbol != expectedSymbols[i] {
			t.Errorf("alert %d: got symbol %q, want %q", i, alert.Symbol, expectedSymbols[i])
		}
	}
}

func TestNewAlertsSinceKeepsLatestPerSymbol(t *testing.T) {
	// Previous run at 2026-06-08 09:29:00 EDT
	previousRun := time.Date(2026, 6, 8, 9, 29, 0, 0, stockChartsTimeZone)

	alerts := []json.RawMessage{
		json.RawMessage(`{
			"symbol": "$COMPQ",
			"bearish": "yes",
			"alert": "Nasdaq crosses below 25800",
			"lastfired": "8 Jun 2026, 9:30am"
		}`),
		json.RawMessage(`{
			"symbol": "$COMPQ",
			"bearish": "no",
			"alert": "Nasdaq crosses above 25800",
			"lastfired": "8 Jun 2026, 9:33am"
		}`),
		json.RawMessage(`{
			"symbol": "$COMPQ",
			"bearish": "no",
			"alert": "Nasdaq crosses above 25900",
			"lastfired": "8 Jun 2026, 9:33am"
		}`),
		json.RawMessage(`{
			"symbol": "$GOLD",
			"bearish": "yes",
			"alert": "Gold crosses below 4400",
			"lastfired": "8 Jun 2026, 9:30am"
		}`),
	}

	result := NewAlertsSince(alerts, previousRun)

	if len(result) != 3 {
		t.Errorf("got %d alerts, want 3", len(result))
	}

	expectedAlerts := []string{
		"Nasdaq crosses above 25800",
		"Nasdaq crosses above 25900",
		"Gold crosses below 4400",
	}
	for i, alert := range result {
		if i < len(expectedAlerts) && alert.Alert != expectedAlerts[i] {
			t.Errorf("alert %d: got %q, want %q", i, alert.Alert, expectedAlerts[i])
		}
	}
}

func TestParseStockChartsTime(t *testing.T) {
	tests := []struct {
		name        string
		input       string
		expectedRFC string
		shouldError bool
	}{
		{
			name:        "lowercase_am_pm_no_space",
			input:       "31 Jul 2024, 2:31pm",
			expectedRFC: "2024-07-31T14:31:00-04:00",
			shouldError: false,
		},
		{
			name:        "uppercase_am_pm_with_space",
			input:       "1 Aug 2024, 8:11 AM",
			expectedRFC: "2024-08-01T08:11:00-04:00",
			shouldError: false,
		},
		{
			name:        "uppercase_am_pm_with_space_and_et_suffix",
			input:       "1 Aug 2024, 8:11 AM ET",
			expectedRFC: "2024-08-01T08:11:00-04:00",
			shouldError: false,
		},
		{
			name:        "lowercase_am_pm_with_et_suffix",
			input:       "31 Jul 2024, 2:31pm ET",
			expectedRFC: "2024-07-31T14:31:00-04:00",
			shouldError: false,
		},
		{
			name:        "single_digit_day_and_hour",
			input:       "1 Aug 2024, 8:11 AM",
			expectedRFC: "2024-08-01T08:11:00-04:00",
			shouldError: false,
		},
		{
			name:        "dst_fall_back_ambiguity_picks_earliest",
			input:       "3 Nov 2024, 1:30am",
			expectedRFC: "2024-11-03T01:30:00-04:00",
			shouldError: false,
		},
		{
			name:        "invalid_format",
			input:       "invalid timestamp",
			shouldError: true,
		},
		{
			name:        "missing_am_pm",
			input:       "31 Jul 2024, 2:31",
			shouldError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := ParseStockChartsTime(tt.input)
			if tt.shouldError {
				if err == nil {
					t.Errorf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			// Verify the result is in the correct timezone.
			if result.Location().String() != stockChartsTimeZone.String() {
				t.Errorf("got timezone %v, want %v", result.Location(), stockChartsTimeZone)
			}

			// Verify the RFC3339 representation matches.
			if result.Format(time.RFC3339) != tt.expectedRFC {
				t.Errorf("got %s, want %s", result.Format(time.RFC3339), tt.expectedRFC)
			}
		})
	}
}

func TestParseStockChartsTimeUsesEasternTime(t *testing.T) {
	parsed, err := ParseStockChartsTime("31 Jul 2024, 2:31pm")
	if err != nil {
		t.Fatalf("parse failed: %v", err)
	}

	if parsed.Location().String() != stockChartsTimeZone.String() {
		t.Errorf("got timezone %v, want %v", parsed.Location(), stockChartsTimeZone)
	}

	if parsed.Format(time.RFC3339) != "2024-07-31T14:31:00-04:00" {
		t.Errorf("got %s, want 2024-07-31T14:31:00-04:00", parsed.Format(time.RFC3339))
	}
}

func TestParseStockChartsTimeHandlesDSTFallAmbiguity(t *testing.T) {
	// 3 Nov 2024, 1:30am is ambiguous in America/New_York.
	// It could be:
	// - 2024-11-03T01:30:00-04:00 (EDT, earlier)
	// - 2024-11-03T01:30:00-05:00 (EST, later)
	// We expect the earliest instant (EDT).
	parsed, err := ParseStockChartsTime("3 Nov 2024, 1:30am")
	if err != nil {
		t.Fatalf("parse failed: %v", err)
	}

	if parsed.Format(time.RFC3339) != "2024-11-03T01:30:00-04:00" {
		t.Errorf("got %s, want 2024-11-03T01:30:00-04:00", parsed.Format(time.RFC3339))
	}
}

func TestParseStockChartsTimeTrimsWhitespace(t *testing.T) {
	tests := []struct {
		name  string
		input string
	}{
		{"leading_space", "  31 Jul 2024, 2:31pm"},
		{"trailing_space", "31 Jul 2024, 2:31pm  "},
		{"both_spaces", "  31 Jul 2024, 2:31pm  "},
		{"et_suffix_with_spaces", "31 Jul 2024, 2:31pm ET  "},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := ParseStockChartsTime(tt.input)
			if err != nil {
				t.Fatalf("parse failed: %v", err)
			}
			if result.Format(time.RFC3339) != "2024-07-31T14:31:00-04:00" {
				t.Errorf("got %s, want 2024-07-31T14:31:00-04:00", result.Format(time.RFC3339))
			}
		})
	}
}

func TestFilterAlertsWithMalformedJSON(t *testing.T) {
	// Test that malformed JSON is skipped with a warning.
	alerts := []json.RawMessage{
		json.RawMessage(`{"alert": "Valid alert", "lastfired": "31 Jul 2024, 2:31pm", "symbol": "$TEST"}`),
		json.RawMessage(`{invalid json}`),
		json.RawMessage(`{"alert": "Another valid", "lastfired": "31 Jul 2024, 2:31pm"}`),
	}

	result := FilterAlerts(alerts)
	if len(result) != 2 {
		t.Errorf("got %d alerts, want 2", len(result))
	}
}

func TestNewAlertsSinceWithParseErrors(t *testing.T) {
	// Test that alerts with unparseable timestamps are skipped.
	previousRun := time.Date(2024, 7, 31, 12, 0, 0, 0, stockChartsTimeZone)

	alerts := []json.RawMessage{
		json.RawMessage(`{
			"symbol": "$VALID",
			"alert": "Valid alert",
			"lastfired": "31 Jul 2024, 2:31pm"
		}`),
		json.RawMessage(`{
			"symbol": "$INVALID",
			"alert": "Invalid timestamp",
			"lastfired": "invalid timestamp"
		}`),
	}

	result := NewAlertsSince(alerts, previousRun)
	if len(result) != 1 {
		t.Errorf("got %d alerts, want 1", len(result))
	}
	if result[0].Symbol != "$VALID" {
		t.Errorf("got symbol %q, want $VALID", result[0].Symbol)
	}
}

func TestUnmarshalJSONWithNullFields(t *testing.T) {
	// Test that null fields are handled correctly.
	input := `{
		"alert": "Test",
		"bearish": null,
		"lastfired": "31 Jul 2024, 2:31pm",
		"symbol": null
	}`

	var alert Alert
	if err := json.Unmarshal([]byte(input), &alert); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}

	if alert.Bearish != "no" {
		t.Errorf("null bearish should default to 'no', got %q", alert.Bearish)
	}
	if alert.Symbol != "UNKNOWN" {
		t.Errorf("null symbol should default to 'UNKNOWN', got %q", alert.Symbol)
	}
}

func TestStockChartsTimeZone(t *testing.T) {
	// Test that StockChartsTimeZone returns a valid timezone.
	loc := StockChartsTimeZone()
	if loc == nil {
		t.Fatal("StockChartsTimeZone() returned nil")
	}

	// Verify it's the correct timezone
	if loc.String() != "America/New_York" {
		t.Errorf("expected timezone America/New_York, got %s", loc.String())
	}

	// Verify it can be used to parse times
	now := time.Now().In(loc)
	if now.Location().String() != "America/New_York" {
		t.Errorf("time.In() did not apply the timezone correctly")
	}
}
