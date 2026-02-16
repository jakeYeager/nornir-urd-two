"""Tests for nornir_urd.decluster module."""

import pytest

from nornir_urd.decluster import (
    decluster_gardner_knopoff,
    gk_window,
    haversine_km,
)


class TestHaversine:
    def test_same_point(self):
        assert haversine_km(0.0, 0.0, 0.0, 0.0) == 0.0

    def test_known_distance(self):
        # London (51.5074, -0.1278) to Paris (48.8566, 2.3522) ≈ 343 km
        dist = haversine_km(51.5074, -0.1278, 48.8566, 2.3522)
        assert 340 < dist < 346

    def test_antipodal(self):
        # North pole to south pole ≈ half circumference ≈ 20015 km
        dist = haversine_km(90.0, 0.0, -90.0, 0.0)
        assert 20010 < dist < 20020

    def test_symmetric(self):
        d1 = haversine_km(10.0, 20.0, 30.0, 40.0)
        d2 = haversine_km(30.0, 40.0, 10.0, 20.0)
        assert abs(d1 - d2) < 1e-9


class TestGKWindow:
    def test_m6_windows(self):
        dist, time = gk_window(6.0)
        # G-K 1974: d = 10^(0.1238*6 + 0.983) ≈ 54 km
        assert 50 < dist < 60
        # G-K 1974 (M < 6.5): t = 10^(0.5409*6 - 0.547) ≈ 499 days
        assert 450 < time < 550

    def test_m7_windows(self):
        dist, time = gk_window(7.0)
        # d = 10^(0.1238*7 + 0.983) ≈ 70 km
        assert 65 < dist < 80
        # M >= 6.5: t = 10^(0.032*7 + 2.7389) ≈ 915 days
        assert 850 < time < 1000

    def test_larger_mag_larger_window(self):
        d5, t5 = gk_window(5.0)
        d6, t6 = gk_window(6.0)
        d7, t7 = gk_window(7.0)
        assert d5 < d6 < d7
        assert t5 < t6 < t7


class TestDecluster:
    def test_empty_catalog(self):
        main, after = decluster_gardner_knopoff([])
        assert main == []
        assert after == []

    def test_single_event(self):
        events = [
            {
                "usgs_id": "ev1",
                "usgs_mag": 6.5,
                "event_at": "2026-01-15T12:00:00Z",
                "latitude": 35.0,
                "longitude": 139.0,
            },
        ]
        main, after = decluster_gardner_knopoff(events)
        assert len(main) == 1
        assert len(after) == 0
        assert main[0]["usgs_id"] == "ev1"

    def test_close_aftershock_flagged(self):
        """A smaller event close in space and time to a larger event is an aftershock."""
        events = [
            {
                "usgs_id": "mainshock",
                "usgs_mag": 7.0,
                "event_at": "2026-01-15T12:00:00Z",
                "latitude": 35.0,
                "longitude": 139.0,
            },
            {
                "usgs_id": "aftershock",
                "usgs_mag": 5.5,
                "event_at": "2026-01-15T14:00:00Z",  # 2 hours later
                "latitude": 35.1,
                "longitude": 139.1,  # ~14 km away
            },
        ]
        main, after = decluster_gardner_knopoff(events)
        assert len(main) == 1
        assert main[0]["usgs_id"] == "mainshock"
        assert len(after) == 1
        assert after[0]["usgs_id"] == "aftershock"

    def test_distant_event_not_flagged(self):
        """An event far away is not flagged even if close in time."""
        events = [
            {
                "usgs_id": "ev1",
                "usgs_mag": 7.0,
                "event_at": "2026-01-15T12:00:00Z",
                "latitude": 35.0,
                "longitude": 139.0,
            },
            {
                "usgs_id": "ev2",
                "usgs_mag": 6.0,
                "event_at": "2026-01-15T14:00:00Z",
                "latitude": -33.0,
                "longitude": -70.0,  # Chile — thousands of km away
            },
        ]
        main, after = decluster_gardner_knopoff(events)
        assert len(main) == 2
        assert len(after) == 0

    def test_temporally_distant_not_flagged(self):
        """An event close in space but far in time is not flagged."""
        events = [
            {
                "usgs_id": "ev1",
                "usgs_mag": 6.0,
                "event_at": "2020-01-15T12:00:00Z",
                "latitude": 35.0,
                "longitude": 139.0,
            },
            {
                "usgs_id": "ev2",
                "usgs_mag": 5.5,
                "event_at": "2026-01-15T12:00:00Z",  # 6 years later
                "latitude": 35.05,
                "longitude": 139.05,
            },
        ]
        main, after = decluster_gardner_knopoff(events)
        assert len(main) == 2
        assert len(after) == 0

    def test_equal_magnitude_can_be_flagged(self):
        """An event of equal magnitude within the window is flagged as dependent."""
        events = [
            {
                "usgs_id": "ev1",
                "usgs_mag": 6.5,
                "event_at": "2026-01-15T12:00:00Z",
                "latitude": 35.0,
                "longitude": 139.0,
            },
            {
                "usgs_id": "ev2",
                "usgs_mag": 6.5,
                "event_at": "2026-01-15T13:00:00Z",  # 1 hour later
                "latitude": 35.05,
                "longitude": 139.05,
            },
        ]
        main, after = decluster_gardner_knopoff(events)
        # One should be mainshock, one dependent (first processed keeps priority)
        assert len(main) == 1
        assert len(after) == 1

    def test_preserves_extra_keys(self):
        """Extra dict keys beyond the required ones are preserved."""
        events = [
            {
                "usgs_id": "ev1",
                "usgs_mag": 6.5,
                "event_at": "2026-01-15T12:00:00Z",
                "latitude": 35.0,
                "longitude": 139.0,
                "depth": 25.0,
                "custom_field": "hello",
            },
        ]
        main, _ = decluster_gardner_knopoff(events)
        assert main[0]["depth"] == 25.0
        assert main[0]["custom_field"] == "hello"

    def test_foreshock_flagged(self):
        """A smaller event before the mainshock within the window is flagged."""
        events = [
            {
                "usgs_id": "foreshock",
                "usgs_mag": 5.0,
                "event_at": "2026-01-15T10:00:00Z",  # 2 hours before
                "latitude": 35.05,
                "longitude": 139.05,
            },
            {
                "usgs_id": "mainshock",
                "usgs_mag": 7.0,
                "event_at": "2026-01-15T12:00:00Z",
                "latitude": 35.0,
                "longitude": 139.0,
            },
        ]
        main, after = decluster_gardner_knopoff(events)
        assert len(main) == 1
        assert main[0]["usgs_id"] == "mainshock"
        assert len(after) == 1
        assert after[0]["usgs_id"] == "foreshock"
