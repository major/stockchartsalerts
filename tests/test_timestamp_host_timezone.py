"""Timestamp parsing must not depend on the host's local timezone."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import stockchartsalerts


@pytest.mark.parametrize("host_timezone", ["UTC", "America/Bogota"])
def test_nonexistent_timestamp_uses_eastern_time_in_any_host_timezone(
    host_timezone: str,
) -> None:
    """Normalize a spring-forward gap to Eastern time regardless of host TZ."""
    parsed_in_test_process = stockchartsalerts.parse_timestamp("10 Mar 2024, 2:30am")
    assert parsed_in_test_process.isoformat() == "2024-03-10T01:30:00-05:00"

    child_environment = os.environ.copy()
    child_environment["TZ"] = host_timezone
    package_source = str(Path(stockchartsalerts.__file__).resolve().parent.parent)
    python_paths = [package_source]
    if inherited_pythonpath := child_environment.get("PYTHONPATH"):
        python_paths.append(inherited_pythonpath)
    child_environment["PYTHONPATH"] = os.pathsep.join(python_paths)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json
import time
from datetime import timezone
from stockchartsalerts import parse_timestamp

if hasattr(time, "tzset"):
    time.tzset()

parsed = parse_timestamp("10 Mar 2024, 2:30am")
print(json.dumps({
    "timezone": str(parsed.tzinfo),
    "eastern": parsed.isoformat(),
    "utc": parsed.astimezone(timezone.utc).isoformat(),
}))
""",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=child_environment,
        timeout=10,
    )

    assert json.loads(result.stdout) == {
        "timezone": "America/New_York",
        "eastern": "2024-03-10T01:30:00-05:00",
        "utc": "2024-03-10T06:30:00+00:00",
    }
