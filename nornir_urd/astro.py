"""Astronomical calculations for earthquake data enrichment.

Pre-computes solstice and new moon tables using Skyfield, then provides
functions to calculate solar_secs, lunar_secs, and midnight_secs for any
earthquake event.
"""

from __future__ import annotations

import bisect
import math
from datetime import datetime, timezone

from skyfield import almanac
from skyfield.api import load


def _load_ephemeris():
    """Load the Skyfield ephemeris and timescale."""
    ts = load.timescale()
    eph = load("de421.bsp")
    return ts, eph


def build_solstice_table(
    start_year: int = 1948, end_year: int = 2051
) -> list[datetime]:
    """Return sorted UTC datetimes of all December solstices in [start_year, end_year)."""
    ts, eph = _load_ephemeris()
    t0 = ts.utc(start_year, 1, 1)
    t1 = ts.utc(end_year, 1, 1)

    season_at = almanac.seasons(eph)
    times, indices = almanac.find_discrete(t0, t1, season_at)

    # Season index 3 = Winter/December solstice
    solstices = [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t, idx in zip(times, indices)
        if idx == 3
    ]
    return sorted(solstices)


def build_new_moon_table(
    start_year: int = 1948, end_year: int = 2051
) -> list[datetime]:
    """Return sorted UTC datetimes of all new moons in [start_year, end_year)."""
    ts, eph = _load_ephemeris()
    t0 = ts.utc(start_year, 1, 1)
    t1 = ts.utc(end_year, 1, 1)

    moon_phase_at = almanac.moon_phases(eph)
    times, indices = almanac.find_discrete(t0, t1, moon_phase_at)

    # Phase index 0 = New Moon
    new_moons = [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t, idx in zip(times, indices)
        if idx == 0
    ]
    return sorted(new_moons)


def solar_secs(
    event_at: datetime, solstice_table: list[datetime]
) -> tuple[int, int]:
    """Seconds since the preceding December solstice.

    Returns (solaration_year, solar_secs) where solaration_year is the
    calendar year following the December solstice that precedes the event.
    """
    if event_at.tzinfo is None:
        event_at = event_at.replace(tzinfo=timezone.utc)

    idx = bisect.bisect_right(solstice_table, event_at) - 1
    if idx < 0:
        raise ValueError(
            f"Event {event_at} is before the first solstice in the table"
        )

    preceding_solstice = solstice_table[idx]
    delta = event_at - preceding_solstice
    secs = int(delta.total_seconds())
    solaration_year = preceding_solstice.year + 1
    return solaration_year, secs


def lunar_secs(event_at: datetime, new_moon_table: list[datetime]) -> int:
    """Seconds since the preceding new moon."""
    if event_at.tzinfo is None:
        event_at = event_at.replace(tzinfo=timezone.utc)

    idx = bisect.bisect_right(new_moon_table, event_at) - 1
    if idx < 0:
        raise ValueError(
            f"Event {event_at} is before the first new moon in the table"
        )

    preceding_new_moon = new_moon_table[idx]
    delta = event_at - preceding_new_moon
    return int(delta.total_seconds())


def midnight_secs(event_at: datetime, longitude: float) -> int:
    """Seconds since the most recent local solar midnight.

    Local solar midnight is approximated using a simple longitude-based
    offset: local_time = UTC + longitude/360 * 86400 seconds.
    """
    if event_at.tzinfo is None:
        event_at = event_at.replace(tzinfo=timezone.utc)

    # Seconds since UTC midnight on the event's UTC date
    utc_midnight = event_at.replace(hour=0, minute=0, second=0, microsecond=0)
    utc_secs_since_midnight = (event_at - utc_midnight).total_seconds()

    # Longitude offset in seconds (positive east)
    offset_secs = int(longitude / (360.0 / 86400))

    # Local solar time in seconds since local midnight
    local_secs = (utc_secs_since_midnight + offset_secs) % 86400.0

    return int(local_secs)
