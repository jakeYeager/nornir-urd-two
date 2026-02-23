"""Tests for window-scaled G-K declustering with parent attribution."""

import csv
import io

import pytest

from nornir_urd.cli import build_parser, main
from nornir_urd.decluster import (
    decluster_gardner_knopoff,
    decluster_with_parents,
    gk_window,
    gk_window_scaled,
    haversine_km,
)


# ---------------------------------------------------------------------------
# gk_window_scaled
# ---------------------------------------------------------------------------


class TestGKWindowScaled:
    def test_scale_0_75_reduces_both_dimensions(self):
        dist_std, time_std = gk_window(6.0)
        dist_s, time_s = gk_window_scaled(6.0, 0.75)
        assert abs(dist_s - dist_std * 0.75) < 1e-9
        assert abs(time_s - time_std * 0.75) < 1e-9

    def test_scale_1_25_increases_both_dimensions(self):
        dist_std, time_std = gk_window(6.0)
        dist_s, time_s = gk_window_scaled(6.0, 1.25)
        assert abs(dist_s - dist_std * 1.25) < 1e-9
        assert abs(time_s - time_std * 1.25) < 1e-9

    def test_scale_1_0_matches_standard(self):
        for mag in [5.0, 6.0, 6.5, 7.0, 8.0]:
            dist_std, time_std = gk_window(mag)
            dist_s, time_s = gk_window_scaled(mag, 1.0)
            assert abs(dist_s - dist_std) < 1e-9
            assert abs(time_s - time_std) < 1e-9


# ---------------------------------------------------------------------------
# decluster_with_parents — helpers
# ---------------------------------------------------------------------------


def _pair():
    """One mainshock + one spatially/temporally close aftershock."""
    return [
        {
            "usgs_id": "main1",
            "usgs_mag": 7.0,
            "event_at": "2026-01-15T12:00:00Z",
            "latitude": 35.0,
            "longitude": 139.0,
        },
        {
            "usgs_id": "after1",
            "usgs_mag": 5.5,
            "event_at": "2026-01-15T14:00:00Z",  # 7200 sec later
            "latitude": 35.1,
            "longitude": 139.1,  # ~13.3 km away
        },
    ]


# ---------------------------------------------------------------------------
# decluster_with_parents — trivial cases
# ---------------------------------------------------------------------------


class TestDeclusterWithParentsTrivial:
    def test_empty_catalog(self):
        main, after = decluster_with_parents([])
        assert main == []
        assert after == []

    def test_single_event_is_mainshock(self):
        events = [
            {
                "usgs_id": "ev1",
                "usgs_mag": 6.5,
                "event_at": "2026-01-15T12:00:00Z",
                "latitude": 35.0,
                "longitude": 139.0,
            }
        ]
        main, after = decluster_with_parents(events)
        assert len(main) == 1
        assert len(after) == 0


# ---------------------------------------------------------------------------
# decluster_with_parents — parity with standard algorithm at scale=1.0
# ---------------------------------------------------------------------------


class TestDeclusterWithParentsScale1:
    def test_matches_standard_classification(self):
        """window_scale=1.0 must produce the same mainshock/aftershock split."""
        events = _pair()
        main_std, after_std = decluster_gardner_knopoff(events)
        main_w, after_w = decluster_with_parents(events, window_scale=1.0)
        assert {e["usgs_id"] for e in main_std} == {e["usgs_id"] for e in main_w}
        assert {e["usgs_id"] for e in after_std} == {e["usgs_id"] for e in after_w}


# ---------------------------------------------------------------------------
# decluster_with_parents — parent attribution columns
# ---------------------------------------------------------------------------


class TestParentAttribution:
    def test_parent_columns_present(self):
        _, aftershocks = decluster_with_parents(_pair())
        assert len(aftershocks) == 1
        after = aftershocks[0]
        assert "parent_id" in after
        assert "parent_magnitude" in after
        assert "delta_t_sec" in after
        assert "delta_dist_km" in after

    def test_parent_id_correct(self):
        _, aftershocks = decluster_with_parents(_pair())
        assert aftershocks[0]["parent_id"] == "main1"

    def test_parent_magnitude_correct(self):
        _, aftershocks = decluster_with_parents(_pair())
        assert aftershocks[0]["parent_magnitude"] == 7.0

    def test_delta_t_sec_positive_for_aftershock(self):
        """Aftershock occurs after parent → delta_t_sec is positive."""
        _, aftershocks = decluster_with_parents(_pair())
        # after1 is 7200 seconds after main1
        assert abs(aftershocks[0]["delta_t_sec"] - 7200.0) < 1.0

    def test_delta_t_sec_negative_for_foreshock(self):
        """Foreshock occurs before parent → delta_t_sec is negative."""
        events = [
            {
                "usgs_id": "foreshock",
                "usgs_mag": 5.0,
                "event_at": "2026-01-15T10:00:00Z",  # 7200 sec before mainshock
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
        _, aftershocks = decluster_with_parents(events)
        assert len(aftershocks) == 1
        assert aftershocks[0]["usgs_id"] == "foreshock"
        assert aftershocks[0]["delta_t_sec"] < 0

    def test_delta_dist_km_value(self):
        """delta_dist_km matches the haversine distance between aftershock and parent."""
        _, aftershocks = decluster_with_parents(_pair())
        expected = haversine_km(35.0, 139.0, 35.1, 139.1)
        assert abs(aftershocks[0]["delta_dist_km"] - expected) < 1e-6

    def test_mainshocks_have_no_extra_columns(self):
        mainshocks, _ = decluster_with_parents(_pair())
        for m in mainshocks:
            assert "parent_id" not in m
            assert "parent_magnitude" not in m
            assert "delta_t_sec" not in m
            assert "delta_dist_km" not in m


# ---------------------------------------------------------------------------
# decluster_with_parents — tight / wide window population effects
# ---------------------------------------------------------------------------


class TestWindowScalePopulation:
    # M6.0 standard windows: dist ≈ 53.2 km, time ≈ 499 days
    # 0.75×: dist ≈ 39.9 km, time ≈ 374 days
    # 1.25×: dist ≈ 66.5 km, time ≈ 624 days
    #
    # Border event at ~44.7 km, 400 days:
    #   standard  (53.2 km, 499 d): 44.7 < 53.2 AND 400 < 499  → INSIDE  → flagged
    #   0.75×     (39.9 km, 374 d): 44.7 > 39.9                → OUTSIDE → not flagged
    #
    # Border event at ~44.7 km, 520 days:
    #   standard  (53.2 km, 499 d): 520 > 499                  → OUTSIDE → not flagged
    #   1.25×     (66.5 km, 624 d): 44.7 < 66.5 AND 520 < 624 → INSIDE  → flagged

    _MAIN = {
        "usgs_id": "main",
        "usgs_mag": 6.0,
        "event_at": "2020-01-01T00:00:00Z",
        "latitude": 35.0,
        "longitude": 139.0,
    }

    def test_tight_window_misses_border_event(self):
        """0.75× does not flag an event just inside the standard window."""
        # 400 days from 2020-01-01 = 2021-02-03; ~44.7 km at lon 139.49
        border = {
            "usgs_id": "border",
            "usgs_mag": 5.0,
            "event_at": "2021-02-03T00:00:00Z",
            "latitude": 35.0,
            "longitude": 139.49,
        }
        events = [self._MAIN, border]
        _, after_tight = decluster_with_parents(events, window_scale=0.75)
        _, after_std = decluster_with_parents(events, window_scale=1.0)
        assert len(after_std) == 1
        assert len(after_tight) == 0

    def test_wide_window_catches_border_event(self):
        """1.25× flags an event just outside the standard time window."""
        # 520 days from 2020-01-01 = 2021-06-04; ~44.7 km at lon 139.49
        border = {
            "usgs_id": "border",
            "usgs_mag": 5.0,
            "event_at": "2021-06-04T00:00:00Z",
            "latitude": 35.0,
            "longitude": 139.49,
        }
        events = [self._MAIN, border]
        _, after_wide = decluster_with_parents(events, window_scale=1.25)
        _, after_std = decluster_with_parents(events, window_scale=1.0)
        assert len(after_std) == 0
        assert len(after_wide) == 1


# ---------------------------------------------------------------------------
# decluster_with_parents — overlapping window / parent re-assignment
# ---------------------------------------------------------------------------


class TestOverlapResolution:
    def test_closer_parent_wins(self):
        """When two mainshocks both cover the same dependent event,
        the one with the smallest |delta_t_sec| is assigned as parent.

        Timeline (days from 2020-01-01):
          A ─────────────────── C ───── B
          0                    600    1000

        |dt(A, C)| = 600 days  — A claims C first (M7.0 processed before M6.8)
        |dt(B, C)| = 400 days  — B re-claims C (closer in time)

        A and B do not claim each other: |dt(A, B)| = 1000 days, which exceeds
        both the M7.0 window (~918 days) and the M6.8 window (~905 days).
        """
        events = [
            {
                "usgs_id": "main_A",
                "usgs_mag": 7.0,
                "event_at": "2020-01-01T00:00:00Z",
                "latitude": 35.0,
                "longitude": 139.0,
            },
            {
                # 1000 days after A: 2022-09-26
                "usgs_id": "main_B",
                "usgs_mag": 6.8,
                "event_at": "2022-09-26T00:00:00Z",
                "latitude": 35.0,
                "longitude": 139.1,
            },
            {
                # 600 days after A (400 days before B): 2021-08-22
                "usgs_id": "dep_C",
                "usgs_mag": 5.5,
                "event_at": "2021-08-22T00:00:00Z",
                "latitude": 35.05,
                "longitude": 139.05,
            },
        ]
        main, after = decluster_with_parents(events, window_scale=1.0)
        assert len(main) == 2
        assert {e["usgs_id"] for e in main} == {"main_A", "main_B"}
        assert len(after) == 1
        assert after[0]["usgs_id"] == "dep_C"
        # B is 400 days from C; A is 600 days from C — B wins
        assert after[0]["parent_id"] == "main_B"

    def test_closer_parent_delta_t_is_negative(self):
        """When the winning parent is AFTER the dependent event, delta_t_sec < 0."""
        # dep_C is 400 days BEFORE main_B → signed delta = -400 days
        events = [
            {
                "usgs_id": "main_A",
                "usgs_mag": 7.0,
                "event_at": "2020-01-01T00:00:00Z",
                "latitude": 35.0,
                "longitude": 139.0,
            },
            {
                "usgs_id": "main_B",
                "usgs_mag": 6.8,
                "event_at": "2022-09-26T00:00:00Z",
                "latitude": 35.0,
                "longitude": 139.1,
            },
            {
                "usgs_id": "dep_C",
                "usgs_mag": 5.5,
                "event_at": "2021-08-22T00:00:00Z",
                "latitude": 35.05,
                "longitude": 139.05,
            },
        ]
        _, after = decluster_with_parents(events, window_scale=1.0)
        assert after[0]["parent_id"] == "main_B"
        # C is before B → negative delta_t
        assert after[0]["delta_t_sec"] < 0
        # |delta_t| ≈ 400 days = 34 560 000 sec
        assert abs(abs(after[0]["delta_t_sec"]) - 400 * 86400) < 86400  # within 1 day


# ---------------------------------------------------------------------------
# CLI integration — window subcommand
# ---------------------------------------------------------------------------


class TestWindowCLI:
    def _write_csv(self, path, rows, fieldnames):
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_window_produces_four_extra_columns(self, tmp_path):
        input_path = tmp_path / "events.csv"
        mainshocks_path = tmp_path / "main.csv"
        aftershocks_path = tmp_path / "after.csv"

        fieldnames = ["usgs_id", "usgs_mag", "event_at", "latitude", "longitude", "depth"]
        rows = [
            {
                "usgs_id": "main1", "usgs_mag": 7.0,
                "event_at": "2026-01-15T12:00:00Z",
                "latitude": 35.0, "longitude": 139.0, "depth": 10.0,
            },
            {
                "usgs_id": "after1", "usgs_mag": 5.5,
                "event_at": "2026-01-15T14:00:00Z",
                "latitude": 35.1, "longitude": 139.1, "depth": 8.0,
            },
        ]
        self._write_csv(input_path, rows, fieldnames)

        main(
            [
                "window",
                "--window-size", "1.0",
                "--input", str(input_path),
                "--mainshocks", str(mainshocks_path),
                "--aftershocks", str(aftershocks_path),
            ]
        )

        with open(aftershocks_path, newline="") as f:
            reader = csv.DictReader(f)
            after_rows = list(reader)

        assert len(after_rows) == 1
        assert "parent_id" in after_rows[0]
        assert "parent_magnitude" in after_rows[0]
        assert "delta_t_sec" in after_rows[0]
        assert "delta_dist_km" in after_rows[0]
        assert after_rows[0]["parent_id"] == "main1"

    def test_mainshock_output_has_no_extra_columns(self, tmp_path):
        input_path = tmp_path / "events.csv"
        mainshocks_path = tmp_path / "main.csv"
        aftershocks_path = tmp_path / "after.csv"

        fieldnames = ["usgs_id", "usgs_mag", "event_at", "latitude", "longitude", "depth"]
        rows = [
            {
                "usgs_id": "main1", "usgs_mag": 7.0,
                "event_at": "2026-01-15T12:00:00Z",
                "latitude": 35.0, "longitude": 139.0, "depth": 10.0,
            },
            {
                "usgs_id": "after1", "usgs_mag": 5.5,
                "event_at": "2026-01-15T14:00:00Z",
                "latitude": 35.1, "longitude": 139.1, "depth": 8.0,
            },
        ]
        self._write_csv(input_path, rows, fieldnames)

        main(
            [
                "window",
                "--window-size", "1.0",
                "--input", str(input_path),
                "--mainshocks", str(mainshocks_path),
                "--aftershocks", str(aftershocks_path),
            ]
        )

        with open(mainshocks_path, newline="") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == fieldnames
