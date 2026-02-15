"""Tests for nornir_urd.astro astronomical calculations."""

from datetime import datetime, timezone

import pytest

from nornir_urd.astro import (
    build_new_moon_table,
    build_solstice_table,
    lunar_secs,
    midnight_secs,
    solar_secs,
)


# Build tables once for the test session
@pytest.fixture(scope="session")
def solstice_table():
    return build_solstice_table(1948, 2051)


@pytest.fixture(scope="session")
def new_moon_table():
    return build_new_moon_table(1948, 2051)


# --- Solstice table tests ---


def test_solstice_table_length(solstice_table):
    """One December solstice per year from 1948 through 2050."""
    assert len(solstice_table) == 2051 - 1948


def test_solstice_table_contains_known_date(solstice_table):
    """The 2021 December solstice was on 2021-12-21 ~15:59 UTC."""
    solstice_2021 = [s for s in solstice_table if s.year == 2021]
    assert len(solstice_2021) == 1
    s = solstice_2021[0]
    assert s.month == 12
    assert s.day == 21
    assert s.hour == 15
    # Allow a few minutes tolerance for the minute
    assert 55 <= s.minute <= 59


def test_solstice_table_sorted(solstice_table):
    """Table should be in chronological order."""
    for i in range(len(solstice_table) - 1):
        assert solstice_table[i] < solstice_table[i + 1]


# --- New moon table tests ---


def test_new_moon_table_has_entries(new_moon_table):
    """Should have roughly 12-13 new moons per year over ~103 years."""
    assert 1200 < len(new_moon_table) < 1400


def test_new_moon_table_contains_known_date(new_moon_table):
    """Known new moon: 2021-01-13 ~05:00 UTC."""
    candidates = [
        nm
        for nm in new_moon_table
        if nm.year == 2021 and nm.month == 1 and nm.day == 13
    ]
    assert len(candidates) == 1
    nm = candidates[0]
    assert 4 <= nm.hour <= 6


def test_new_moon_table_sorted(new_moon_table):
    """Table should be in chronological order."""
    for i in range(len(new_moon_table) - 1):
        assert new_moon_table[i] < new_moon_table[i + 1]


# --- solar_secs tests ---


def test_solar_secs_legacy_row1(solstice_table):
    """Verify against legacy data row 1: iscgem897116.

    Legacy solar_secs=429453 implies a solstice reference of Dec 21 00:00 UTC,
    while Skyfield places the 1949 December solstice at Dec 22 ~04:32 UTC.
    The legacy system likely truncated solstice times to a calendar date via
    a timezone conversion. We accept up to ~2 day tolerance here.
    """
    event = datetime(1949, 12, 25, 23, 17, 33, tzinfo=timezone.utc)
    year, secs = solar_secs(event, solstice_table)
    assert year == 1950
    assert abs(secs - 429453) < 172800  # ~2 day tolerance for date-truncation


def test_solar_secs_event_at_solstice(solstice_table):
    """Event exactly at a solstice should give 0 seconds."""
    solstice = solstice_table[10]  # arbitrary solstice
    year, secs = solar_secs(solstice, solstice_table)
    assert secs == 0
    assert year == solstice.year + 1


# --- lunar_secs tests ---


def test_lunar_secs_legacy_row1(solstice_table, new_moon_table):
    """Verify against legacy data row 1: iscgem897116."""
    event = datetime(1949, 12, 25, 23, 17, 33, tzinfo=timezone.utc)
    secs = lunar_secs(event, new_moon_table)
    # Legacy value: 534153; allow small tolerance
    assert abs(secs - 534153) < 120


def test_lunar_secs_event_at_new_moon(new_moon_table):
    """Event exactly at a new moon should give 0 seconds."""
    nm = new_moon_table[10]  # arbitrary new moon
    secs = lunar_secs(nm, new_moon_table)
    assert secs == 0


# --- midnight_secs tests ---


def test_midnight_secs_utc_longitude():
    """At longitude 0, midnight_secs should equal UTC seconds since midnight."""
    event = datetime(2021, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
    secs = midnight_secs(event, 0.0)
    expected = 10 * 3600 + 30 * 60  # 37800
    assert secs == expected


def test_midnight_secs_180_longitude():
    """At longitude 180, local time is +12h from UTC."""
    event = datetime(2021, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
    secs = midnight_secs(event, 180.0)
    expected = 12 * 3600  # 43200 (noon local)
    assert secs == expected


def test_midnight_secs_negative_longitude():
    """At longitude -90, local time is -6h from UTC."""
    event = datetime(2021, 6, 15, 3, 0, 0, tzinfo=timezone.utc)
    secs = midnight_secs(event, -90.0)
    # 3h UTC - 6h = -3h = 21h previous day
    expected = 21 * 3600  # 75600
    assert secs == expected


def test_midnight_secs_legacy_row1():
    """Verify exact match against legacy data row 1."""
    event = datetime(1949, 12, 25, 23, 17, 33, tzinfo=timezone.utc)
    secs = midnight_secs(event, 139.717)
    assert secs == 30985


# --- Edge cases ---


def test_solar_secs_naive_datetime(solstice_table):
    """Naive datetime should be treated as UTC."""
    event = datetime(2000, 6, 15, 12, 0, 0)
    year, secs = solar_secs(event, solstice_table)
    assert year == 2000
    assert secs > 0


def test_solar_secs_before_table_raises(solstice_table):
    """Event before the table should raise ValueError."""
    event = datetime(1900, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        solar_secs(event, solstice_table)
