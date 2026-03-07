"""Tests for nornir_urd.ocean module."""

import csv
import random

import pytest

from nornir_urd.ocean import (
    CONTINENTAL,
    OCEANIC,
    TRANSITIONAL,
    _build_sorted_vertex_index,
    _dist_to_nearest_sorted,
    classify_distance,
    classify_events,
    dist_to_nearest_vertex,
    load_coastline_vertices,
    load_pb2002_vertices,
)


# ---------------------------------------------------------------------------
# load_coastline_vertices
# ---------------------------------------------------------------------------

class TestLoadCoastlineVertices:
    def test_loads_numeric_rows(self, tmp_path):
        p = tmp_path / "coast.csv"
        p.write_text("10.5,20.3\n-15.0,35.7\n")
        verts = load_coastline_vertices(str(p))
        assert verts == [(10.5, 20.3), (-15.0, 35.7)]

    def test_skips_header_row(self, tmp_path):
        p = tmp_path / "coast.csv"
        p.write_text("lon,lat\n10.5,20.3\n")
        verts = load_coastline_vertices(str(p))
        assert verts == [(10.5, 20.3)]

    def test_skips_short_rows(self, tmp_path):
        p = tmp_path / "coast.csv"
        p.write_text("10.5\n10.5,20.3\n")
        verts = load_coastline_vertices(str(p))
        assert verts == [(10.5, 20.3)]

    def test_empty_file(self, tmp_path):
        p = tmp_path / "coast.csv"
        p.write_text("")
        verts = load_coastline_vertices(str(p))
        assert verts == []


# ---------------------------------------------------------------------------
# load_pb2002_vertices
# ---------------------------------------------------------------------------

class TestLoadPb2002Vertices:
    def test_loads_lon_lat_columns(self, tmp_path):
        p = tmp_path / "types.csv"
        p.write_text("segment_id,plate_a,plate_b,boundary_type_code,boundary_type_label,lon,lat\n"
                     "1,AF,AN,CTF,Continental transform fault,19.162,-72.209\n")
        verts = load_pb2002_vertices(str(p))
        assert verts == [(19.162, -72.209)]

    def test_skips_malformed_rows(self, tmp_path):
        p = tmp_path / "types.csv"
        p.write_text("segment_id,plate_a,plate_b,boundary_type_code,boundary_type_label,lon,lat\n"
                     "bad,AF,AN,CTF,label,not_a_number,-72.209\n"
                     "1,AF,AN,CTF,label,19.162,-72.209\n")
        verts = load_pb2002_vertices(str(p))
        assert len(verts) == 1

    def test_empty_file(self, tmp_path):
        p = tmp_path / "types.csv"
        p.write_text("segment_id,plate_a,plate_b,boundary_type_code,boundary_type_label,lon,lat\n")
        verts = load_pb2002_vertices(str(p))
        assert verts == []


# ---------------------------------------------------------------------------
# dist_to_nearest_vertex
# ---------------------------------------------------------------------------

class TestDistToNearestVertex:
    def test_zero_distance_to_self(self):
        verts = [(10.0, 20.0)]
        d = dist_to_nearest_vertex(20.0, 10.0, verts)
        assert d == pytest.approx(0.0, abs=1e-6)

    def test_picks_closest_vertex(self):
        near = (0.0, 0.1)   # ~11 km away
        far = (0.0, 10.0)   # ~1111 km away
        d = dist_to_nearest_vertex(0.0, 0.0, [near, far])
        assert d < 20.0  # definitely closer to near than far

    def test_known_distance(self):
        # London (51.5, -0.1) to Paris (48.85, 2.35) ≈ 340 km
        verts = [(2.35, 48.85)]
        d = dist_to_nearest_vertex(51.5, -0.1, verts)
        assert 330.0 < d < 360.0


# ---------------------------------------------------------------------------
# classify_distance
# ---------------------------------------------------------------------------

class TestClassifyDistance:
    def test_oceanic(self):
        assert classify_distance(250.0, 200.0, 50.0) == OCEANIC

    def test_continental(self):
        assert classify_distance(30.0, 200.0, 50.0) == CONTINENTAL

    def test_exact_coastal_threshold_is_continental(self):
        assert classify_distance(50.0, 200.0, 50.0) == CONTINENTAL

    def test_just_above_coastal_is_transitional(self):
        assert classify_distance(50.1, 200.0, 50.0) == TRANSITIONAL

    def test_exact_oceanic_threshold_is_transitional(self):
        assert classify_distance(200.0, 200.0, 50.0) == TRANSITIONAL

    def test_just_above_oceanic_is_oceanic(self):
        assert classify_distance(200.1, 200.0, 50.0) == OCEANIC

    def test_transitional_midrange(self):
        assert classify_distance(125.0, 200.0, 50.0) == TRANSITIONAL


# ---------------------------------------------------------------------------
# classify_events
# ---------------------------------------------------------------------------

class TestClassifyEvents:
    _COAST_VERTEX = (0.0, 0.0)  # (lon, lat)

    def _make_event(self, usgs_id, lat, lon):
        return {"usgs_id": usgs_id, "latitude": str(lat), "longitude": str(lon)}

    def test_returns_correct_schema(self):
        events = [self._make_event("eq1", 0.0, 0.0)]
        results = classify_events(events, [self._COAST_VERTEX])
        assert set(results[0].keys()) == {"usgs_id", "ocean_class", "dist_to_coast_km"}

    def test_near_coast_is_continental(self):
        events = [self._make_event("eq1", 0.0, 0.0)]
        results = classify_events(events, [self._COAST_VERTEX], coastal_km=50.0)
        assert results[0]["ocean_class"] == CONTINENTAL

    def test_far_from_coast_is_oceanic(self):
        # Place event ~5500 km from vertex at (0,0): lat 50°N lon 0°
        events = [self._make_event("eq1", 50.0, 0.0)]
        results = classify_events(events, [self._COAST_VERTEX], oceanic_km=200.0)
        assert results[0]["ocean_class"] == OCEANIC

    def test_preserves_usgs_id(self):
        events = [self._make_event("unique-id-123", 0.0, 0.0)]
        results = classify_events(events, [self._COAST_VERTEX])
        assert results[0]["usgs_id"] == "unique-id-123"

    def test_dist_to_coast_is_rounded(self):
        events = [self._make_event("eq1", 0.0, 1.0)]
        results = classify_events(events, [self._COAST_VERTEX])
        dist = results[0]["dist_to_coast_km"]
        # Should be a rounded float, not an infinite string
        assert isinstance(dist, float)
        # 1 degree of longitude at equator ≈ 111 km
        assert 100.0 < dist < 125.0

    def test_empty_catalog(self):
        results = classify_events([], [self._COAST_VERTEX])
        assert results == []

    def test_row_count_matches_input(self):
        events = [self._make_event(f"eq{i}", float(i), 0.0) for i in range(5)]
        results = classify_events(events, [self._COAST_VERTEX])
        assert len(results) == 5


# ---------------------------------------------------------------------------
# _dist_to_nearest_sorted (fast bisect-based path)
# ---------------------------------------------------------------------------

class TestDistToNearestSorted:
    def _sorted(self, verts):
        return _build_sorted_vertex_index(verts)

    def test_empty_returns_inf(self):
        sv, keys = self._sorted([])
        assert _dist_to_nearest_sorted(0.0, 0.0, sv, keys) == float("inf")

    def test_zero_distance_to_self(self):
        sv, keys = self._sorted([(10.0, 20.0)])
        d = _dist_to_nearest_sorted(20.0, 10.0, sv, keys)
        assert d == pytest.approx(0.0, abs=1e-6)

    def test_matches_naive_single_vertex(self):
        verts = [(2.35, 48.85)]  # Paris
        sv, keys = self._sorted(verts)
        naive = dist_to_nearest_vertex(51.5, -0.1, verts)
        fast = _dist_to_nearest_sorted(51.5, -0.1, sv, keys)
        assert fast == pytest.approx(naive, rel=1e-6)

    def test_matches_naive_random_set(self):
        rng = random.Random(42)
        verts = [(rng.uniform(-180, 180), rng.uniform(-90, 90)) for _ in range(200)]
        lat, lon = 35.0, -120.0
        naive = dist_to_nearest_vertex(lat, lon, verts)
        sv, keys = self._sorted(verts)
        fast = _dist_to_nearest_sorted(lat, lon, sv, keys)
        assert fast == pytest.approx(naive, rel=1e-6)

    def test_matches_naive_lat_beyond_all_vertices(self):
        """Query point latitude above every vertex in the list."""
        verts = [(0.0, -80.0), (10.0, -70.0), (20.0, -60.0)]
        lat, lon = 89.0, 0.0  # near North Pole
        naive = dist_to_nearest_vertex(lat, lon, verts)
        sv, keys = self._sorted(verts)
        fast = _dist_to_nearest_sorted(lat, lon, sv, keys)
        assert fast == pytest.approx(naive, rel=1e-6)

    def test_matches_naive_lat_below_all_vertices(self):
        """Query point latitude below every vertex in the list."""
        verts = [(0.0, 10.0), (10.0, 20.0), (20.0, 30.0)]
        lat, lon = -89.0, 0.0  # near South Pole
        naive = dist_to_nearest_vertex(lat, lon, verts)
        sv, keys = self._sorted(verts)
        fast = _dist_to_nearest_sorted(lat, lon, sv, keys)
        assert fast == pytest.approx(naive, rel=1e-6)


# ---------------------------------------------------------------------------
# classify_events – progress callback
# ---------------------------------------------------------------------------

class TestClassifyEventsProgress:
    _COAST_VERTEX = (0.0, 0.0)

    def _make_event(self, usgs_id, lat, lon):
        return {"usgs_id": usgs_id, "latitude": str(lat), "longitude": str(lon)}

    def test_progress_called_once_per_event(self):
        calls = []
        events = [self._make_event(f"eq{i}", float(i), 0.0) for i in range(5)]
        classify_events(events, [self._COAST_VERTEX], progress=lambda c, t: calls.append((c, t)))
        assert len(calls) == 5

    def test_progress_current_values_are_sequential(self):
        calls = []
        n = 4
        events = [self._make_event(f"eq{i}", float(i), 0.0) for i in range(n)]
        classify_events(events, [self._COAST_VERTEX], progress=lambda c, t: calls.append((c, t)))
        assert [c for c, _ in calls] == list(range(1, n + 1))

    def test_progress_total_is_constant(self):
        calls = []
        n = 3
        events = [self._make_event(f"eq{i}", float(i), 0.0) for i in range(n)]
        classify_events(events, [self._COAST_VERTEX], progress=lambda c, t: calls.append((c, t)))
        assert all(t == n for _, t in calls)

    def test_progress_none_does_not_raise(self):
        events = [self._make_event("eq1", 0.0, 0.0)]
        results = classify_events(events, [self._COAST_VERTEX], progress=None)
        assert len(results) == 1

    def test_progress_not_called_for_empty_catalog(self):
        calls = []
        classify_events([], [self._COAST_VERTEX], progress=lambda c, t: calls.append((c, t)))
        assert calls == []
