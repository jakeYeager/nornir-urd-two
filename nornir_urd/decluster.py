"""Gardner-Knopoff (1974) earthquake declustering.

Separates a catalog into mainshocks and aftershocks/foreshocks using
magnitude-dependent space-time windows from Gardner & Knopoff (1974).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Callable

EARTH_RADIUS_KM = 6371.0

# Discrete lookup table from Gardner & Knopoff (1974), Table 1.
# Each row: (minimum magnitude, spatial window km, temporal window days).
# Rows are ordered descending so the first matching threshold is used.
# NOTE: Verify these values against the original 1974 paper before use in
# production analysis. The continuous formula in gk_window() is independent.
_GK_TABLE: list[tuple[float, float, float]] = [
    (7.0, 70.0, 985.0),
    (6.5, 61.0, 960.0),
    (6.0, 54.0, 915.0),
    (5.5, 47.0, 790.0),
    (5.0, 40.0, 510.0),
    (4.5, 35.0, 290.0),
    (4.0, 30.0, 155.0),
    (3.5, 26.0,  83.0),
    (3.0, 22.5,  42.0),
    (2.5, 19.5,  22.0),
]


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


def gk_window_table(magnitude: float) -> tuple[float, float]:
    """Return G-K (1974) space and time windows using the discrete lookup table.

    Uses the original table values from Gardner & Knopoff (1974) directly,
    NOT the continuous empirical formula used by gk_window(). Returns the
    window row for the highest magnitude threshold that does not exceed the
    event magnitude. Events below M=2.5 use the M=2.5 row as a floor.

    Returns:
        (distance_km, time_days)
    """
    for threshold, dist_km, time_days in _GK_TABLE:
        if magnitude >= threshold:
            return dist_km, time_days
    return 19.5, 22.0  # M < 2.5: apply M=2.5 row as floor


def gk_window_scaled(magnitude: float, scale: float) -> tuple[float, float]:
    """Return G-K (1974) space and time windows multiplied by *scale*.

    Returns:
        (distance_km, time_days) -- both dimensions scaled by the factor.
    """
    distance_km, time_days = gk_window(magnitude)
    return distance_km * scale, time_days * scale


def _parse_event_time(event_at: str) -> datetime:
    """Parse an ISO 8601 event_at string to a tz-aware datetime."""
    return datetime.fromisoformat(event_at.replace("Z", "+00:00"))


def _gk_decluster_core(
    events: list[dict],
    window_fn: Callable[[float], tuple[float, float]],
) -> tuple[list[dict], list[dict]]:
    """Core G-K declustering with a pluggable window function.

    Processes events in descending magnitude order. For each mainshock
    candidate, flags all spatially and temporally proximate smaller events
    as dependent (aftershock/foreshock).

    Args:
        events:    List of event dicts with event_at, latitude, longitude,
                   usgs_mag (numeric).
        window_fn: Callable(magnitude) -> (dist_km, time_days).

    Returns:
        (mainshocks, aftershocks)
    """
    if not events:
        return [], []

    n = len(events)
    times = [_parse_event_time(e["event_at"]) for e in events]
    indices_by_mag = sorted(range(n), key=lambda i: events[i]["usgs_mag"], reverse=True)
    is_dependent = [False] * n

    for idx in indices_by_mag:
        if is_dependent[idx]:
            continue

        mag = events[idx]["usgs_mag"]
        lat = events[idx]["latitude"]
        lon = events[idx]["longitude"]
        t = times[idx]
        dist_window, time_window = window_fn(mag)
        time_window_secs = time_window * 86400.0

        for j in range(n):
            if j == idx or is_dependent[j]:
                continue
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


def decluster_gardner_knopoff(
    events: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Decluster a catalog using the Gardner-Knopoff (1974) continuous formula.

    Each event dict must contain at minimum:
        event_at  -- ISO 8601 timestamp (str)
        latitude  -- float
        longitude -- float
        usgs_mag  -- float

    Any additional keys are preserved in the output.

    Returns:
        (mainshocks, aftershocks) -- two lists of event dicts.
    """
    return _gk_decluster_core(events, gk_window)


def decluster_gardner_knopoff_table(
    events: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Decluster using the G-K (1974) discrete lookup table (not the formula).

    Identical algorithm to decluster_gardner_knopoff but uses gk_window_table()
    for spatial and temporal windows. The table values are taken directly from
    Gardner & Knopoff (1974) and differ from the continuous formula, particularly
    for the temporal window at M < 6.5.

    Each event dict must contain at minimum:
        event_at  -- ISO 8601 timestamp (str)
        latitude  -- float
        longitude -- float
        usgs_mag  -- float

    Returns:
        (mainshocks, aftershocks) -- two lists of event dicts.
    """
    return _gk_decluster_core(events, gk_window_table)


def decluster_a1b_fixed(
    events: list[dict],
    radius_km: float = 83.2,
    window_days: float = 95.6,
) -> tuple[list[dict], list[dict]]:
    """Decluster using A1b-informed fixed spatial and temporal windows.

    Applies a constant spatial radius and temporal window to all magnitudes,
    independent of event size. The default values (83.2 km, 95.6 days) are
    derived from the A1b analysis case.

    Each event dict must contain at minimum:
        event_at  -- ISO 8601 timestamp (str)
        latitude  -- float
        longitude -- float
        usgs_mag  -- float

    Args:
        events:      List of event dicts.
        radius_km:   Fixed spatial radius in km (default: 83.2).
        window_days: Fixed temporal window in days (default: 95.6).

    Returns:
        (mainshocks, aftershocks) -- two lists of event dicts.
    """
    return _gk_decluster_core(events, lambda _mag: (radius_km, window_days))


def decluster_with_parents(
    events: list[dict],
    window_scale: float = 1.0,
) -> tuple[list[dict], list[dict]]:
    """Decluster using G-K (1974) with scaled windows and per-aftershock parent attribution.

    Each dependent event dict is extended with four attribution columns:
        parent_id        -- usgs_id of the triggering mainshock
        parent_magnitude -- usgs_mag of the triggering mainshock
        delta_t_sec      -- signed elapsed seconds from parent to this event
                           (negative when this event precedes the parent)
        delta_dist_km    -- great-circle distance in km between this event and its parent

    When two mainshock windows overlap and both could claim the same dependent event,
    the parent is the mainshock with the smallest |delta_t_sec| (temporal proximity).

    Args:
        events:       List of event dicts; must contain event_at, latitude,
                      longitude, usgs_id, usgs_mag.
        window_scale: Scalar multiplier applied to both G-K spatial and temporal
                      windows (e.g. 0.75 for tighter, 1.25 for wider).

    Returns:
        (mainshocks, aftershocks) -- mainshocks are unmodified event dicts;
        aftershock dicts carry the four extra attribution keys.
    """
    if not events:
        return [], []

    n = len(events)
    times = [_parse_event_time(e["event_at"]) for e in events]
    indices_by_mag = sorted(range(n), key=lambda i: events[i]["usgs_mag"], reverse=True)

    is_dependent = [False] * n
    parent_idx: list[int | None] = [None] * n
    parent_dt_abs = [float("inf")] * n  # |delta_t_sec| for current best parent

    for idx in indices_by_mag:
        if is_dependent[idx]:
            continue

        mag = events[idx]["usgs_mag"]
        lat = events[idx]["latitude"]
        lon = events[idx]["longitude"]
        t = times[idx]
        dist_window, time_window = gk_window_scaled(mag, window_scale)
        time_window_secs = time_window * 86400.0

        for j in range(n):
            if j == idx:
                continue
            if events[j]["usgs_mag"] > mag:
                continue

            dt_abs = abs((times[j] - t).total_seconds())
            if dt_abs > time_window_secs:
                continue

            dist = haversine_km(lat, lon, events[j]["latitude"], events[j]["longitude"])
            if dist > dist_window:
                continue

            if not is_dependent[j]:
                is_dependent[j] = True
                parent_idx[j] = idx
                parent_dt_abs[j] = dt_abs
            elif dt_abs < parent_dt_abs[j]:
                # Re-assign to the temporally closer mainshock
                parent_idx[j] = idx
                parent_dt_abs[j] = dt_abs

    mainshocks = [e for i, e in enumerate(events) if not is_dependent[i]]
    aftershocks = []
    for i, e in enumerate(events):
        if not is_dependent[i]:
            continue
        p = parent_idx[i]
        parent = events[p]
        dt_sec = (times[i] - times[p]).total_seconds()
        dist_km = haversine_km(
            parent["latitude"], parent["longitude"],
            e["latitude"], e["longitude"],
        )
        after_event = dict(e)
        after_event["parent_id"] = parent["usgs_id"]
        after_event["parent_magnitude"] = parent["usgs_mag"]
        after_event["delta_t_sec"] = dt_sec
        after_event["delta_dist_km"] = dist_km
        aftershocks.append(after_event)

    return mainshocks, aftershocks
