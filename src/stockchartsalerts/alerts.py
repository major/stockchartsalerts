"""Pure alert normalization, timestamp parsing, and selection rules."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_STOCKCHARTS_TIME_ZONE = ZoneInfo("America/New_York")
_NO_ALERTS_PLACEHOLDER = "There are no alerts today"
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_LOWERCASE_TIMESTAMP = re.compile(
    r"(?P<day>[0-9]{1,2}) +(?P<month>[A-Za-z]{3}) +(?P<year>[0-9]{4}), +"
    r"(?P<hour>[0-9]{1,2}):(?P<minute>[0-9]{2})(?P<period>am|pm)"
)
_UPPERCASE_TIMESTAMP = re.compile(
    r"(?P<day>[0-9]{1,2}) +(?P<month>[A-Za-z]{3}) +(?P<year>[0-9]{4}), +"
    r"(?P<hour>[0-9]{1,2}):(?P<minute>[0-9]{2}) +(?P<period>AM|PM)"
)
_ALERT_FIELDS = frozenset({"alert", "bearish", "lastfired", "symbol"})


@dataclass(frozen=True, slots=True, kw_only=True)
class Alert:
    """A normalized StockCharts alert row."""

    bearish: str
    symbol: str
    alert: str
    lastfired: str


def filter_alerts(rows: Sequence[object]) -> list[Alert]:
    """Normalize object rows and skip malformed rows and the no-alert placeholder."""
    result: list[Alert] = []
    defaults = {"alert": "", "bearish": "no", "lastfired": "", "symbol": "UNKNOWN"}

    for row in rows:
        if not isinstance(row, Mapping):
            continue

        fields: dict[str, object] = {}
        malformed = False
        for key, value in row.items():
            if isinstance(key, str) and key.lower() in _ALERT_FIELDS:
                if value is not None and not isinstance(value, str):
                    malformed = True
                    break
                fields[key.lower()] = value

        if malformed:
            continue

        normalized: dict[str, str] = {}
        for name, default in defaults.items():
            value = fields.get(name)
            if isinstance(value, str):
                normalized[name] = value.strip() or default
            else:
                normalized[name] = default

        if normalized["alert"] == _NO_ALERTS_PLACEHOLDER:
            continue

        result.append(
            Alert(
                bearish=normalized["bearish"],
                symbol=normalized["symbol"],
                alert=normalized["alert"],
                lastfired=normalized["lastfired"],
            )
        )

    return result


def parse_timestamp(text: str) -> datetime:
    """Parse a StockCharts timestamp into aware Eastern Time.

    The accepted forms match Go's StockCharts layouts: lowercase ``am``/``pm``
    without a preceding space, or uppercase ``AM``/``PM`` with one. A trailing
    case-sensitive `` ET`` is optional. Ambiguous fall-back times use fold 0;
    nonexistent spring-forward times follow Go's backward normalization.
    """
    if not isinstance(text, str):
        raise ValueError("unsupported StockCharts timestamp")

    cleaned = text.strip()
    if cleaned.endswith(" ET"):
        cleaned = cleaned.removesuffix(" ET").strip()

    match = _LOWERCASE_TIMESTAMP.fullmatch(cleaned)
    if match is None:
        match = _UPPERCASE_TIMESTAMP.fullmatch(cleaned)
    if match is None:
        raise ValueError(f"unsupported StockCharts timestamp: {text}")

    parts = match.groupdict()
    month = _MONTHS.get(parts["month"].lower())
    if month is None:
        raise ValueError(f"unsupported StockCharts timestamp: {text}")

    hour = int(parts["hour"])
    minute = int(parts["minute"])
    if not 0 <= hour <= 12 or minute > 59:
        raise ValueError(f"unsupported StockCharts timestamp: {text}")

    hour = hour % 12 + (12 if parts["period"].lower() == "pm" else 0)
    try:
        wall_time = datetime(
            int(parts["year"]),
            month,
            int(parts["day"]),
            hour,
            minute,
        )
    except ValueError as error:
        raise ValueError(f"unsupported StockCharts timestamp: {text}") from error

    parsed = wall_time.replace(tzinfo=_STOCKCHARTS_TIME_ZONE, fold=0)
    round_trip = parsed.astimezone(timezone.utc).astimezone(_STOCKCHARTS_TIME_ZONE)
    if round_trip.replace(tzinfo=None) != wall_time:
        old_offset = parsed.utcoffset()
        new_offset = wall_time.replace(tzinfo=_STOCKCHARTS_TIME_ZONE, fold=1).utcoffset()
        if old_offset is not None and new_offset is not None:
            gap = new_offset - old_offset
            if gap > timedelta(0):
                parsed = (wall_time - gap).replace(tzinfo=_STOCKCHARTS_TIME_ZONE, fold=0)

    return parsed


def new_alerts_since(alerts: Sequence[Alert], previous_run: datetime) -> list[Alert]:
    """Return strictly newer alerts, keeping all newest-time ties per symbol."""
    if previous_run.tzinfo is None or previous_run.utcoffset() is None:
        raise ValueError("previous_run must be timezone-aware")
    previous_instant = previous_run.astimezone(timezone.utc)

    newer: list[tuple[Alert, datetime]] = []
    for alert in alerts:
        try:
            fired_at = parse_timestamp(alert.lastfired).astimezone(timezone.utc)
        except ValueError:
            continue
        if fired_at > previous_instant:
            newer.append((alert, fired_at))

    newest_by_symbol: dict[str, datetime] = {}
    for alert, fired_at in newer:
        newest = newest_by_symbol.get(alert.symbol)
        if newest is None or fired_at > newest:
            newest_by_symbol[alert.symbol] = fired_at

    return [alert for alert, fired_at in newer if fired_at == newest_by_symbol[alert.symbol]]
