"""Property checks for alert selection and webhook normalization."""

from datetime import datetime, timedelta
from string import ascii_letters, digits
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from hypothesis import given
from hypothesis import strategies as st

from stockchartsalerts import Alert, load_settings, new_alerts_since

if TYPE_CHECKING:
    from collections.abc import Sequence

_EASTERN = ZoneInfo("America/New_York")
_ANCHOR = datetime(2024, 8, 1, 12, tzinfo=_EASTERN)
_HOURS_PER_HALF_DAY = 12


def _format_minutes_after_anchor(minutes: int) -> str:
    fired_at = _ANCHOR + timedelta(minutes=minutes)
    hour = fired_at.hour % _HOURS_PER_HALF_DAY or _HOURS_PER_HALF_DAY
    period = "am" if fired_at.hour < _HOURS_PER_HALF_DAY else "pm"
    return f"{fired_at.day} Aug 2024, {hour}:{fired_at.minute:02}{period}"


def _make_alerts(rows: Sequence[tuple[str, int]]) -> list[Alert]:
    return [
        Alert(
            bearish="no",
            symbol=symbol,
            alert=f"row-{index}",
            lastfired=_format_minutes_after_anchor(minutes),
        )
        for index, (symbol, minutes) in enumerate(rows)
    ]


def _expected_alert_ids(rows: Sequence[tuple[str, int]]) -> list[str]:
    newer_rows = [(index, symbol, minutes) for index, (symbol, minutes) in enumerate(rows) if minutes > 0]
    newest_by_symbol = {
        symbol: max(minutes for candidate_symbol, minutes in rows if candidate_symbol == symbol and minutes > 0)
        for _, symbol, _ in newer_rows
    }
    return [f"row-{index}" for index, symbol, minutes in newer_rows if minutes == newest_by_symbol[symbol]]


@given(
    tie_minutes=st.integers(min_value=1, max_value=5),
    case_minutes=st.integers(min_value=1, max_value=5),
    extra_rows=st.lists(
        st.tuples(
            st.text(alphabet=ascii_letters, min_size=1, max_size=4),
            st.integers(min_value=-5, max_value=5),
        ),
        max_size=25,
    ),
)
def test_alert_selection_matches_reference_for_generated_ties_and_boundaries(
    tie_minutes: int,
    case_minutes: int,
    extra_rows: list[tuple[str, int]],
) -> None:
    """Keep only strictly newer, latest per-symbol rows in original order."""
    rows = [
        ("TIE", tie_minutes - 1),
        ("ABC", case_minutes),
        ("TIE", tie_minutes),
        ("abc", case_minutes + 1),
        ("ANCHOR", 0),
        ("TIE", tie_minutes),
        ("ABC", case_minutes - 1),
    ]
    rows.extend((f"generated-{symbol}", minutes) for symbol, minutes in extra_rows)

    selected = new_alerts_since(_make_alerts(rows), _ANCHOR)

    assert [alert.alert for alert in selected] == _expected_alert_ids(rows)


def _expected_webhooks(entries: Sequence[str]) -> tuple[str, ...]:
    unique_entries = dict.fromkeys(entry.strip() for entry in entries if entry.strip())
    return tuple(unique_entries)


@given(
    entries=st.lists(
        st.text(alphabet=ascii_letters + digits + ":/_- ", max_size=12),
        max_size=30,
    ),
)
def test_webhook_configuration_normalizes_generated_entries(entries: list[str]) -> None:
    """Trim webhook values, drop blanks, and keep each first occurrence."""
    raw_entries = ["  seed  ", *entries, "", " seed "]
    env: dict[str, str] = {"DISCORD_WEBHOOK_URLS": ",".join(raw_entries)}

    settings = load_settings(env)

    assert settings.webhook_urls == _expected_webhooks(raw_entries)
