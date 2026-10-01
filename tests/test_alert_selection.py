"""Behavior scenarios for StockCharts alert normalization and selection."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from stockchartsalerts import Alert, filter_alerts, new_alerts_since, parse_timestamp
from stockchartsalerts.alerts import select_alerts

ET = ZoneInfo("America/New_York")


@pytest.mark.parametrize(
    "rows",
    [
        pytest.param(
            [
                {"alert": " There are no alerts today "},
                {
                    "alert": "First healthy alert",
                    "lastfired": "31 Jul 2024, 9:30am",
                    "symbol": "FIRST",
                },
                {
                    "alert": "Second healthy alert",
                    "lastfired": "31 Jul 2024, 9:31am",
                    "symbol": "SECOND",
                },
            ],
            id="leading-placeholder",
        ),
        pytest.param(
            [
                {
                    "alert": "First healthy alert",
                    "lastfired": "31 Jul 2024, 9:30am",
                    "symbol": "FIRST",
                },
                {"alert": "There are no alerts today"},
                {
                    "alert": "Second healthy alert",
                    "lastfired": "31 Jul 2024, 9:31am",
                    "symbol": "SECOND",
                },
            ],
            id="middle-placeholder",
        ),
    ],
)
def test_placeholder_does_not_stop_filtering_or_selection(rows: list[object]) -> None:
    """Healthy rows after a placeholder remain selected in input order."""
    expected = ["First healthy alert", "Second healthy alert"]

    filtered = filter_alerts(rows)
    selection = select_alerts(rows, datetime(2024, 7, 31, 9, 29, tzinfo=ET))

    assert [alert.alert for alert in filtered] == expected
    assert [alert.alert for alert in selection.selected] == expected
    assert selection.malformed_rows == 0
    assert selection.invalid_timestamps == 0


def test_feed_selection_normalizes_rows_and_discards_invalid_alerts() -> None:
    """Normalize valid feed rows before applying the time-based selection."""
    rows = [
        {
            "alert": "  Crossed above 10  ",
            "bearish": " yes ",
            "lastfired": " 31 Jul 2024, 2:31pm ",
            "symbol": " $COMPQ ",
            "unknown": 12,
        },
        {"bearish": None, "symbol": None, "alert": None, "lastfired": None},
        {"ALERT": " Alert ", "SYMBOL": " $ABC "},
        {"bearish": None, "symbol": None, "alert": None, "lastfired": "31 Jul 2024, 2:30pm"},
        {"alert": "There are no alerts today"},
        None,
        ["not", "an", "object"],
        {"alert": 123},
        {"bearish": False},
        {"lastfired": []},
        {"symbol": {}},
        {"alert": 123, "Alert": "valid alert"},
    ]
    normalized = [
        Alert(
            bearish="yes",
            symbol="$COMPQ",
            alert="Crossed above 10",
            lastfired="31 Jul 2024, 2:31pm",
        ),
        Alert(bearish="no", symbol="UNKNOWN", alert="", lastfired=""),
        Alert(bearish="no", symbol="$ABC", alert="Alert", lastfired=""),
        Alert(bearish="no", symbol="UNKNOWN", alert="", lastfired="31 Jul 2024, 2:30pm"),
    ]

    assert filter_alerts(rows) == normalized
    assert new_alerts_since(normalized, datetime(2024, 7, 31, 2, 29, tzinfo=ET)) == [
        normalized[0],
        normalized[3],
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("31 Jul 2024, 2:31pm", "2024-07-31T14:31:00-04:00"),
        ("31  Jul   2024,  2:31pm", "2024-07-31T14:31:00-04:00"),
        ("1 Aug 2024, 8:11 AM", "2024-08-01T08:11:00-04:00"),
        ("1 Aug 2024, 8:11   AM", "2024-08-01T08:11:00-04:00"),
        ("1 Aug 2024, 8:11 AM ET", "2024-08-01T08:11:00-04:00"),
        ("  1 aug 2024, 08:11am ET  ", "2024-08-01T08:11:00-04:00"),
        ("1 Aug 2024, 0:11am", "2024-08-01T00:11:00-04:00"),
        ("1 Jan 2024, 12:00am", "2024-01-01T00:00:00-05:00"),
        ("1 Jan 2024, 12:00pm", "2024-01-01T12:00:00-05:00"),
        ("3 Nov 2024, 1:30am", "2024-11-03T01:30:00-04:00"),
        ("10 Mar 2024, 2:30am", "2024-03-10T01:30:00-05:00"),
    ],
)
def test_stockcharts_timestamp_formats_use_eastern_time(text: str, expected: str) -> None:
    """Accepted timestamp layouts resolve to the expected Eastern instant."""
    parsed = parse_timestamp(text)

    assert parsed.tzinfo is ET or parsed.tzinfo == ET
    assert parsed.isoformat() == expected


@pytest.mark.parametrize(
    "text",
    [
        "31 Jul 2024, 2:31 pm",
        "31 Jul 2024, 2:31PM",
        "31 Jul 2024, 2:3pm",
        "31 Jul 2024, 13:31pm",
        "31 Jul 2024, 2:60pm",
        "31 Jul 2024, 2:31pm et",
        "31 Jul 2024, 2:31pm EDT",
        "31 Jul 2024, 2:31pm ET extra",
        "31 July 2024, 2:31pm",
        "31 Jul 2024 2:31pm",
        "not a timestamp",
    ],
)
def test_stockcharts_timestamp_formats_reject_near_matches(text: str) -> None:
    """Near-matches outside StockCharts' supported layouts are rejected."""
    with pytest.raises(ValueError):
        parse_timestamp(text)


def test_stockcharts_timestamp_rejects_unrepresentable_utc_conversion() -> None:
    """Eastern timestamps that overflow when converted to UTC raise ValueError."""
    with pytest.raises(ValueError, match="unsupported StockCharts timestamp"):
        parse_timestamp("31 Dec 9999, 11:59pm")


def test_lookback_selection_keeps_latest_alerts_and_all_timestamp_ties() -> None:
    """Emit only strictly newer rows at each symbol's latest timestamp."""
    alerts = [
        Alert(bearish="no", symbol="A", alert="old", lastfired="31 Jul 2024, 9:30am"),
        Alert(bearish="no", symbol="B", alert="other", lastfired="31 Jul 2024, 9:31am"),
        Alert(bearish="no", symbol="a", alert="lowercase symbol", lastfired="31 Jul 2024, 9:31am"),
        Alert(bearish="yes", symbol="A", alert="new first", lastfired="31 Jul 2024, 9:32am"),
        Alert(bearish="no", symbol="A", alert="new tie", lastfired="31 Jul 2024, 9:32am"),
        Alert(bearish="no", symbol="C", alert="equal anchor", lastfired="31 Jul 2024, 9:29am"),
        Alert(bearish="no", symbol="D", alert="invalid time", lastfired="invalid"),
    ]

    selected = new_alerts_since(alerts, datetime(2024, 7, 31, 9, 29, tzinfo=ET))

    assert [alert.alert for alert in selected] == [
        "other",
        "lowercase symbol",
        "new first",
        "new tie",
    ]


def test_lookback_selection_compares_fall_back_occurrences_by_instant() -> None:
    """The first ambiguous clock reading can be older than the anchor."""
    alert = Alert(
        bearish="no",
        symbol="A",
        alert="earlier occurrence",
        lastfired="3 Nov 2024, 1:30am",
    )
    previous_run = datetime(2024, 11, 3, 1, 15, tzinfo=ET, fold=1)

    assert new_alerts_since([alert], previous_run) == []


def test_lookback_selection_requires_a_timezone_aware_anchor() -> None:
    """A naive lookback anchor cannot be compared with StockCharts times."""
    alert = Alert(bearish="no", symbol="A", alert="alert", lastfired="31 Jul 2024, 9:30am")

    with pytest.raises(ValueError, match="timezone-aware"):
        new_alerts_since([alert], datetime.fromisoformat("2024-07-31T09:29"))
