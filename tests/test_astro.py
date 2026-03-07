"""Tests for nornir_urd.astro astronomical calculations."""

from datetime import datetime, timezone

import pytest

from nornir_urd.astro import (
    build_new_moon_table,
    build_solstice_table,
    lunar_secs,
    midnight_secs,
    solar_geometry,
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


def test_solar_secs_event_at_solstice(solstice_table):
    """Event exactly at a solstice should give 0 seconds."""
    solstice = solstice_table[10]  # arbitrary solstice
    year, secs = solar_secs(solstice, solstice_table)
    assert secs == 0
    assert year == solstice.year + 1


# --- lunar_secs tests ---


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


# --- solar_geometry tests ---


def test_solar_geometry_returns_three_floats():
    event = datetime(2000, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
    result = solar_geometry(event)
    assert len(result) == 3
    assert all(isinstance(v, float) for v in result)


def test_solar_geometry_summer_solstice_declination():
    """Near summer solstice, solar declination should be close to +23.5°."""
    event = datetime(2000, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
    dec, _, _ = solar_geometry(event)
    assert 23.0 < dec < 24.0


def test_solar_geometry_winter_solstice_declination():
    """Near December solstice, solar declination should be close to -23.5°."""
    event = datetime(2000, 12, 21, 12, 0, 0, tzinfo=timezone.utc)
    dec, _, _ = solar_geometry(event)
    assert -24.0 < dec < -23.0


def test_solar_geometry_spring_equinox_declination():
    """Near spring equinox, solar declination should be close to 0°."""
    event = datetime(2000, 3, 20, 7, 35, 0, tzinfo=timezone.utc)
    dec, _, _ = solar_geometry(event)
    assert -1.0 < dec < 1.0


def test_solar_geometry_summer_solstice_rate_near_zero():
    """Near summer solstice, declination rate should be near 0 (at maximum)."""
    event = datetime(2000, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
    _, rate, _ = solar_geometry(event)
    assert abs(rate) < 0.05  # degrees/day


def test_solar_geometry_spring_equinox_rate_positive():
    """Near spring equinox, declination is increasing northward (rate > 0)."""
    event = datetime(2000, 3, 20, 7, 35, 0, tzinfo=timezone.utc)
    _, rate, _ = solar_geometry(event)
    assert rate > 0.3  # should be close to max ~0.4°/day


def test_solar_geometry_fall_equinox_rate_negative():
    """Near fall equinox, declination is decreasing southward (rate < 0)."""
    event = datetime(2000, 9, 22, 17, 28, 0, tzinfo=timezone.utc)
    _, rate, _ = solar_geometry(event)
    assert rate < -0.3


def test_solar_geometry_perihelion_distance():
    """Near January perihelion, Earth-Sun distance < 1 AU."""
    event = datetime(2000, 1, 3, 12, 0, 0, tzinfo=timezone.utc)
    _, _, dist = solar_geometry(event)
    assert dist < 0.985


def test_solar_geometry_aphelion_distance():
    """Near July aphelion, Earth-Sun distance > 1 AU."""
    event = datetime(2000, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
    _, _, dist = solar_geometry(event)
    assert dist > 1.015


def test_solar_geometry_distance_in_valid_range():
    """Earth-Sun distance should always be within the annual variation range."""
    event = datetime(2010, 4, 15, 0, 0, 0, tzinfo=timezone.utc)
    _, _, dist = solar_geometry(event)
    assert 0.980 < dist < 1.020


def test_solar_geometry_naive_datetime_treated_as_utc():
    """Naive datetime input should not raise and return valid values."""
    event = datetime(2000, 6, 21, 12, 0, 0)  # no tzinfo
    dec, rate, dist = solar_geometry(event)
    assert 23.0 < dec < 24.0
    assert 0.980 < dist < 1.020
