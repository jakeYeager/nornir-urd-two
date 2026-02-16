"""USGS Earthquake Hazards Program API client."""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta

import httpx

USGS_CSV_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
USGS_ROW_LIMIT = 20_000


def fetch_earthquakes(
    start: date,
    end: date,
    min_mag: float = 6.0,
    max_mag: float = 6.9,
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lon: float | None = None,
    max_lon: float | None = None,
) -> list[dict]:
    """Fetch earthquake events from the USGS API.

    Returns a list of dicts with keys: usgs_id, usgs_mag, event_at, latitude, longitude, depth.
    The event_at value is an ISO 8601 string truncated to whole seconds.
    """
    params: dict[str, str | float] = {
        "format": "csv",
        "eventtype": "earthquake",
        "starttime": start.isoformat(),
        "endtime": end.isoformat(),
        "minmagnitude": min_mag,
        "maxmagnitude": max_mag,
    }
    if min_lat is not None:
        params["minlatitude"] = min_lat
    if max_lat is not None:
        params["maxlatitude"] = max_lat
    if min_lon is not None:
        params["minlongitude"] = min_lon
    if max_lon is not None:
        params["maxlongitude"] = max_lon

    response = httpx.get(USGS_CSV_URL, params=params, timeout=60)
    response.raise_for_status()

    rows = list(csv.DictReader(io.StringIO(response.text)))

    # If we hit the row limit, split the date range and recurse
    if len(rows) >= USGS_ROW_LIMIT:
        mid = start + (end - start) // 2
        if mid == start:
            # Can't split further, return what we have
            return _parse_rows(rows)
        left = fetch_earthquakes(start, mid, min_mag, max_mag,
                                 min_lat, max_lat, min_lon, max_lon)
        right = fetch_earthquakes(mid, end, min_mag, max_mag,
                                  min_lat, max_lat, min_lon, max_lon)
        return left + right

    return _parse_rows(rows)


def _truncate_time(time_str: str) -> str:
    """Truncate a USGS time string to whole seconds.

    '2026-02-12T13:34:31.114Z' -> '2026-02-12T13:34:31Z'
    """
    if "." in time_str and time_str.endswith("Z"):
        return time_str[: time_str.index(".")] + "Z"
    return time_str


def _parse_rows(rows: list[dict]) -> list[dict]:
    """Extract and normalize needed fields from USGS CSV rows."""
    results = []
    for row in rows:
        results.append(
            {
                "usgs_id": row["id"],
                "usgs_mag": float(row["mag"]),
                "event_at": _truncate_time(row["time"]),
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "depth": float(row["depth"]) if row["depth"] != "" else 0.0,
            }
        )
    return results
