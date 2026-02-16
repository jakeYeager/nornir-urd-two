"""Gardner-Knopoff (1974) earthquake declustering.

Separates a catalog into mainshocks and aftershocks/foreshocks using
magnitude-dependent space-time windows from Gardner & Knopoff (1974).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two points using the Haversine formula."""
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def gk_window(magnitude: float) -> tuple[float, float]:
    """Return Gardner-Knopoff (1974) space and time windows for a magnitude.

    Returns:
        (distance_km, time_days) -- the spatial radius and temporal window.

    The original empirical formulas from Gardner & Knopoff (1974):
        distance = 10 ** (0.1238 * M + 0.983)
        time     = 10 ** (0.5409 * M - 0.547)   for M < 6.5
                   10 ** (0.032  * M + 2.7389)   for M >= 6.5
    """
    distance_km = 10 ** (0.1238 * magnitude + 0.983)
    if magnitude >= 6.5:
        time_days = 10 ** (0.032 * magnitude + 2.7389)
    else:
        time_days = 10 ** (0.5409 * magnitude - 0.547)
    return distance_km, time_days


def _parse_event_time(event_at: str) -> datetime:
    """Parse an ISO 8601 event_at string to a tz-aware datetime."""
    return datetime.fromisoformat(event_at.replace("Z", "+00:00"))


def decluster_gardner_knopoff(
    events: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Decluster a catalog using the Gardner-Knopoff (1974) algorithm.

    Each event dict must contain at minimum:
        event_at  -- ISO 8601 timestamp (str)
        latitude  -- float
        longitude -- float
        usgs_mag  -- float

    Any additional keys are preserved in the output.

    Returns:
        (mainshocks, aftershocks) -- two lists of event dicts.
    """
    if not events:
        return [], []

    n = len(events)

    # Pre-compute datetimes and sort indices by magnitude descending
    times = [_parse_event_time(e["event_at"]) for e in events]
    indices_by_mag = sorted(range(n), key=lambda i: events[i]["usgs_mag"], reverse=True)

    # Track which events are flagged as dependent (aftershock/foreshock)
    is_dependent = [False] * n

    for idx in indices_by_mag:
        if is_dependent[idx]:
            continue

        mag = events[idx]["usgs_mag"]
        lat = events[idx]["latitude"]
        lon = events[idx]["longitude"]
        t = times[idx]
        dist_window, time_window = gk_window(mag)
        time_window_secs = time_window * 86400.0

        for j in range(n):
            if j == idx or is_dependent[j]:
                continue
            # Only flag smaller-or-equal magnitude events
            if events[j]["usgs_mag"] > mag:
                continue

            dt_secs = abs((times[j] - t).total_seconds())
            if dt_secs > time_window_secs:
                continue

            dist = haversine_km(lat, lon, events[j]["latitude"], events[j]["longitude"])
            if dist <= dist_window:
                is_dependent[j] = True

    mainshocks = [e for i, e in enumerate(events) if not is_dependent[i]]
    aftershocks = [e for i, e in enumerate(events) if is_dependent[i]]
    return mainshocks, aftershocks
