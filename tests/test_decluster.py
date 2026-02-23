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

    def test_high_latitude(self):
        """At 80°N a 2° longitude gap is only ~38.6 km — meridians converge strongly."""
        dist = haversine_km(80.0, 0.0, 80.0, 2.0)
        assert abs(dist - 38.6) < 1.0

    def test_near_pole(self):
        """At 89°N a 90° longitude gap is only ~157 km — near the pole even large
        longitude differences correspond to short distances."""
        dist = haversine_km(89.0, 0.0, 89.0, 90.0)
        assert 150 < dist < 165

    def test_longitude_wraparound(self):
        """Points straddling the ±180° meridian 0.2° apart are correctly ~22 km apart."""
        dist = haversine_km(0.0, 179.9, 0.0, -179.9)
        assert abs(dist - 22.2) < 1.0


class TestGKWindow:
    def test_m6_windows(self):
        dist, time = gk_window(6.0)
        # G-K 1974: d = 10^(0.1238*6 + 0.983) ≈ 54 km
        assert 50 < dist < 60
        # G-K 1974 (M < 6.5): t = 10^(0.5409*6 - 0.547) ≈ 499 days
        assert 450 < time < 550

    def test_m6_precision(self):
        """M=6.0 windows match reference values to within 1%."""
        dist, time = gk_window(6.0)
        # 10^(0.1238*6 + 0.983) = 10^1.7258 ≈ 53.18 km
        assert abs(dist - 53.2) < 1.0
        # 10^(0.5409*6 - 0.547) = 10^2.6984 ≈ 499.5 days
        assert abs(time - 499) < 5.0

    def test_m7_windows(self):
        dist, time = gk_window(7.0)
        # d = 10^(0.1238*7 + 0.983) ≈ 70 km
        assert 65 < dist < 80
        # M >= 6.5: t = 10^(0.032*7 + 2.7389) ≈ 915 days
        assert 850 < time < 1000

    def test_m7_precision(self):
        """M=7.0 windows match reference values to within 1%."""
        dist, time = gk_window(7.0)
        # 10^(0.1238*7 + 0.983) = 10^1.8496 ≈ 70.73 km
        assert abs(dist - 70.7) < 1.0
        # 10^(0.032*7 + 2.7389) = 10^2.9629 ≈ 918 days
        assert abs(time - 918) < 10.0

    def test_m65_boundary(self):
        """The M=6.5 threshold switches the time formula, creating a discontinuity.

        The M<6.5 branch (steeper slope) grows to ~928 days at M=6.499, then
        the M>=6.5 branch resets to ~885 days at M=6.5. Both branches use the
        same Gardner-Knopoff (1974) empirical formulas fit to separate ranges.
        """
        dist_65, time_65 = gk_window(6.5)
        dist_649, time_649 = gk_window(6.499)
        # M=6.5 uses >= branch: 10^(0.032*6.5 + 2.7389) = 10^2.9469 ≈ 885 days
        assert abs(time_65 - 885) < 10.0
        # M=6.499 uses < branch: 10^(0.5409*6.499 - 0.547) = 10^2.9683 ≈ 928 days
        assert abs(time_649 - 928) < 10.0
        # The M<6.5 branch is steeper: just below 6.5 gives more days than at 6.5
        assert time_649 > time_65
        # Both distances are nearly identical (distance formula has no branch)
        assert abs(dist_649 - dist_65) < 0.2

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

    def test_high_lat_aftershock_flagged(self):
        """At 80°N, an aftershock ~39 km away (large lon diff) is correctly flagged.

        haversine(80, 0, 80, 2) ≈ 38.6 km; M=7.0 window is ~70.7 km — inside.
        """
        events = [
            {
                "usgs_id": "mainshock",
                "usgs_mag": 7.0,
                "event_at": "2026-01-15T12:00:00Z",
                "latitude": 80.0,
                "longitude": 0.0,
            },
            {
                "usgs_id": "aftershock",
                "usgs_mag": 5.5,
                "event_at": "2026-01-15T14:00:00Z",
                "latitude": 80.0,
                "longitude": 2.0,  # ~38.6 km at 80°N, within 70.7 km window
            },
        ]
        main, after = decluster_gardner_knopoff(events)
        assert len(main) == 1
        assert main[0]["usgs_id"] == "mainshock"
        assert len(after) == 1
        assert after[0]["usgs_id"] == "aftershock"

    def test_high_lat_independent_not_flagged(self):
        """At 80°N, an event ~100 km away is outside the M=7.0 window (~70.7 km).

        haversine(80, 0, 80, 5.2) ≈ 100 km — outside window, not flagged.
        """
        events = [
            {
                "usgs_id": "ev1",
                "usgs_mag": 7.0,
                "event_at": "2026-01-15T12:00:00Z",
                "latitude": 80.0,
                "longitude": 0.0,
            },
            {
                "usgs_id": "ev2",
                "usgs_mag": 5.5,
                "event_at": "2026-01-15T14:00:00Z",
                "latitude": 80.0,
                "longitude": 5.2,  # ~100 km at 80°N, outside 70.7 km window
            },
        ]
        main, after = decluster_gardner_knopoff(events)
        assert len(main) == 2
        assert len(after) == 0

    def test_wraparound_aftershock_flagged(self):
        """Events straddling the ±180° meridian ~22 km apart are handled correctly.

        haversine(10, 179.9, 10, -179.9) ≈ 22 km; M=6.5 window is ~61.3 km — inside.
        """
        events = [
            {
                "usgs_id": "mainshock",
                "usgs_mag": 6.5,
                "event_at": "2026-01-15T12:00:00Z",
                "latitude": 10.0,
                "longitude": 179.9,
            },
            {
                "usgs_id": "aftershock",
                "usgs_mag": 5.5,
                "event_at": "2026-01-15T14:00:00Z",
                "latitude": 10.0,
                "longitude": -179.9,  # ~22 km across ±180° meridian
            },
        ]
        main, after = decluster_gardner_knopoff(events)
        assert len(main) == 1
        assert main[0]["usgs_id"] == "mainshock"
        assert len(after) == 1
        assert after[0]["usgs_id"] == "aftershock"
