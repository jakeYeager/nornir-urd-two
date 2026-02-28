"""Tests for nornir_urd.gcmt module."""

import textwrap
from datetime import datetime, timedelta, timezone

import pytest

from nornir_urd.gcmt import (
    APPEND_FIELDNAMES,
    MATCH_NULL,
    MATCH_PROXIMITY,
    NORMAL,
    OBLIQUE,
    STRIKE_SLIP,
    THRUST,
    _gcmt_mw,
    classify_mechanism,
    load_gcmt_dir,
    match_events,
    parse_ndk_records,
)


# ---------------------------------------------------------------------------
# Synthetic NDK content (derived from real jan76_dec20.ndk format)
# ---------------------------------------------------------------------------

# First real record from jan76_dec20.ndk — Kermadec, thrust, exponent=26
_NDK_KERMADEC = textwrap.dedent("""\
    MLI  1976/01/01 01:29:39.6 -28.61 -177.64  59.0 6.2 0.0 KERMADEC ISLANDS REGION
    M010176A         B:  0    0   0 S:  0    0   0 M: 12   30 135 CMT: 1 BOXHD:  9.4
    CENTROID:     13.8 0.2 -29.25 0.02 -176.96 0.01  47.8  0.6 FREE O-00000000000000
    26  7.680 0.090  0.090 0.060 -7.770 0.070  1.390 0.160  4.520 0.160 -3.260 0.060
    V10   8.940 75 283   1.260  2  19 -10.190 15 110   9.560 202 30   93  18 60   88
""")

# Second real record — Peru, normal, exponent=24
_NDK_PERU = textwrap.dedent("""\
    MLI  1976/01/05 02:31:36.3 -13.29  -74.90  95.0 6.0 0.0 PERU
    C010576A         B:  6   14  45 S:  0    0   0 M:  5    8 135 CMT: 1 BOXHD:  1.6
    CENTROID:      8.4 0.4 -13.42 0.07  -75.14 0.06  85.4  3.2 FREE O-00000000000000
    24 -1.780 0.210 -0.590 0.280  2.370 0.280 -1.280 0.150  1.970 0.150 -2.900 0.220
    V10   4.970 19 238  -2.350 14 143  -2.620 66  20   3.790 350 28  -60 137 66 -105
""")

# Iceland — strike-slip, rake=173°, exponent=25
_NDK_ICELAND = textwrap.dedent("""\
    MLI  1976/01/13 13:29:19.5  66.16  -16.58  33.0 6.0 6.4 ICELAND REGION
    C011376A         B:  9   25  45 S:  0    0   0 M: 13   33 135 CMT: 1 BOXHD:  3.4
    CENTROID:      5.4 0.2  66.33 0.02  -16.29 0.04  15.0  0.0 FIX  O-00000000000000
    25 -0.510 0.040 -2.860 0.040  3.370 0.040  0.050 0.160 -0.780 0.200 -0.860 0.040
    V10   3.630 11  82  -0.650 79 255  -2.980  1 352   3.300 127 82  173 218 83    9
""")

_NDK_TWO_EVENTS = _NDK_KERMADEC + _NDK_PERU
_NDK_THREE_EVENTS = _NDK_TWO_EVENTS + _NDK_ICELAND


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_ndk(tmp_path, content, name="test.ndk"):
    p = tmp_path / name
    p.write_text(content)
    return str(p)


def _utc(year, month, day, hour, minute, second, microsecond=0):
    return datetime(year, month, day, hour, minute, second, microsecond,
                    tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# classify_mechanism
# ---------------------------------------------------------------------------

class TestClassifyMechanism:
    def test_pure_thrust(self):
        assert classify_mechanism(90.0) == THRUST

    def test_oblique_thrust_lower_bound(self):
        assert classify_mechanism(45.0) == THRUST

    def test_oblique_thrust_upper_bound(self):
        assert classify_mechanism(135.0) == THRUST

    def test_pure_normal(self):
        assert classify_mechanism(-90.0) == NORMAL

    def test_oblique_normal_lower_bound(self):
        assert classify_mechanism(-135.0) == NORMAL

    def test_oblique_normal_upper_bound(self):
        assert classify_mechanism(-45.0) == NORMAL

    def test_strike_slip_zero(self):
        assert classify_mechanism(0.0) == STRIKE_SLIP

    def test_strike_slip_positive_near_180(self):
        assert classify_mechanism(170.0) == STRIKE_SLIP

    def test_strike_slip_negative_near_180(self):
        assert classify_mechanism(-170.0) == STRIKE_SLIP

    def test_strike_slip_shallow_negative(self):
        assert classify_mechanism(-30.0) == STRIKE_SLIP

    def test_strike_slip_shallow_positive(self):
        assert classify_mechanism(30.0) == STRIKE_SLIP

    def test_rake_normalises_above_180(self):
        # 270° == -90° after normalisation → normal
        assert classify_mechanism(270.0) == NORMAL

    def test_rake_normalises_below_neg180(self):
        # -270° == 90° → thrust
        assert classify_mechanism(-270.0) == THRUST

    def test_iceland_rake_173_is_strike_slip(self):
        assert classify_mechanism(173.0) == STRIKE_SLIP

    def test_peru_rake_neg60_is_normal(self):
        assert classify_mechanism(-60.0) == NORMAL

    def test_kermadec_rake_93_is_thrust(self):
        assert classify_mechanism(93.0) == THRUST


# ---------------------------------------------------------------------------
# parse_ndk_records
# ---------------------------------------------------------------------------

class TestParseNdkRecords:
    def test_returns_list(self, tmp_path):
        path = _write_ndk(tmp_path, _NDK_KERMADEC)
        assert isinstance(parse_ndk_records(path), list)

    def test_single_record_count(self, tmp_path):
        path = _write_ndk(tmp_path, _NDK_KERMADEC)
        assert len(parse_ndk_records(path)) == 1

    def test_two_record_count(self, tmp_path):
        path = _write_ndk(tmp_path, _NDK_TWO_EVENTS)
        assert len(parse_ndk_records(path)) == 2

    def test_gcmt_id_extracted(self, tmp_path):
        path = _write_ndk(tmp_path, _NDK_KERMADEC)
        rec = parse_ndk_records(path)[0]
        assert rec["gcmt_id"] == "M010176A"

    def test_second_gcmt_id(self, tmp_path):
        path = _write_ndk(tmp_path, _NDK_PERU)
        rec = parse_ndk_records(path)[0]
        assert rec["gcmt_id"] == "C010576A"

    def test_centroid_lat(self, tmp_path):
        path = _write_ndk(tmp_path, _NDK_KERMADEC)
        rec = parse_ndk_records(path)[0]
        assert rec["cen_lat"] == pytest.approx(-29.25)

    def test_centroid_lon(self, tmp_path):
        path = _write_ndk(tmp_path, _NDK_KERMADEC)
        rec = parse_ndk_records(path)[0]
        assert rec["cen_lon"] == pytest.approx(-176.96)

    def test_centroid_depth(self, tmp_path):
        path = _write_ndk(tmp_path, _NDK_KERMADEC)
        rec = parse_ndk_records(path)[0]
        assert rec["cen_depth"] == pytest.approx(47.8)

    def test_centroid_time_includes_shift(self, tmp_path):
        """cen_time = ref_time + time_shift (13.8 s for Kermadec)."""
        path = _write_ndk(tmp_path, _NDK_KERMADEC)
        rec = parse_ndk_records(path)[0]
        ref = _utc(1976, 1, 1, 1, 29, 39, 600000)
        expected = ref + timedelta(seconds=13.8)
        assert abs((rec["cen_time"] - expected).total_seconds()) < 0.01

    def test_scalar_moment_kermadec(self, tmp_path):
        """M0 = 9.560 × 10^26 dyne-cm for Kermadec."""
        path = _write_ndk(tmp_path, _NDK_KERMADEC)
        rec = parse_ndk_records(path)[0]
        expected = 9.560e26
        assert rec["scalar_moment"] == pytest.approx(expected, rel=1e-3)

    def test_scalar_moment_peru(self, tmp_path):
        """M0 = 3.790 × 10^24 dyne-cm for Peru."""
        path = _write_ndk(tmp_path, _NDK_PERU)
        rec = parse_ndk_records(path)[0]
        expected = 3.790e24
        assert rec["scalar_moment"] == pytest.approx(expected, rel=1e-3)

    def test_np1_strike(self, tmp_path):
        path = _write_ndk(tmp_path, _NDK_KERMADEC)
        rec = parse_ndk_records(path)[0]
        assert rec["strike"] == 202

    def test_np1_dip(self, tmp_path):
        path = _write_ndk(tmp_path, _NDK_KERMADEC)
        rec = parse_ndk_records(path)[0]
        assert rec["dip"] == 30

    def test_np1_rake(self, tmp_path):
        path = _write_ndk(tmp_path, _NDK_KERMADEC)
        rec = parse_ndk_records(path)[0]
        assert rec["rake"] == 93

    def test_mechanism_thrust(self, tmp_path):
        path = _write_ndk(tmp_path, _NDK_KERMADEC)
        rec = parse_ndk_records(path)[0]
        assert rec["mechanism"] == THRUST

    def test_mechanism_normal(self, tmp_path):
        path = _write_ndk(tmp_path, _NDK_PERU)
        rec = parse_ndk_records(path)[0]
        assert rec["mechanism"] == NORMAL

    def test_mechanism_strike_slip(self, tmp_path):
        path = _write_ndk(tmp_path, _NDK_ICELAND)
        rec = parse_ndk_records(path)[0]
        assert rec["mechanism"] == STRIKE_SLIP

    def test_empty_file(self, tmp_path):
        path = _write_ndk(tmp_path, "")
        assert parse_ndk_records(path) == []

    def test_malformed_record_skipped(self, tmp_path):
        bad = "BAD LINE\nBAD LINE\nBAD LINE\nBAD LINE\nBAD LINE\n"
        path = _write_ndk(tmp_path, bad)
        assert parse_ndk_records(path) == []

    def test_malformed_followed_by_good(self, tmp_path):
        """A bad 5-line group followed by a valid record should yield 1 result."""
        bad = "BAD LINE\nBAD LINE\nBAD LINE\nBAD LINE\nBAD LINE\n"
        path = _write_ndk(tmp_path, bad + _NDK_KERMADEC)
        assert len(parse_ndk_records(path)) == 1


# ---------------------------------------------------------------------------
# load_gcmt_dir
# ---------------------------------------------------------------------------

class TestLoadGcmtDir:
    def test_loads_single_file(self, tmp_path):
        _write_ndk(tmp_path, _NDK_TWO_EVENTS)
        recs = load_gcmt_dir(str(tmp_path))
        assert len(recs) == 2

    def test_merges_multiple_files(self, tmp_path):
        _write_ndk(tmp_path, _NDK_KERMADEC, "a.ndk")
        _write_ndk(tmp_path, _NDK_PERU, "b.ndk")
        recs = load_gcmt_dir(str(tmp_path))
        assert len(recs) == 2

    def test_sorted_by_cen_time(self, tmp_path):
        # Peru (Jan 5) written first in file b, Kermadec (Jan 1) in file a
        _write_ndk(tmp_path, _NDK_PERU, "a.ndk")
        _write_ndk(tmp_path, _NDK_KERMADEC, "b.ndk")
        recs = load_gcmt_dir(str(tmp_path))
        assert recs[0]["gcmt_id"] == "M010176A"  # Jan 1 first
        assert recs[1]["gcmt_id"] == "C010576A"  # Jan 5 second

    def test_ignores_non_ndk_files(self, tmp_path):
        (tmp_path / "readme.txt").write_text("not an ndk file\n")
        _write_ndk(tmp_path, _NDK_KERMADEC)
        recs = load_gcmt_dir(str(tmp_path))
        assert len(recs) == 1

    def test_empty_directory(self, tmp_path):
        recs = load_gcmt_dir(str(tmp_path))
        assert recs == []


# ---------------------------------------------------------------------------
# match_events
# ---------------------------------------------------------------------------

def _make_iscgem(usgs_id, event_at, latitude, longitude, usgs_mag):
    return {
        "usgs_id": usgs_id,
        "event_at": event_at,
        "latitude": str(latitude),
        "longitude": str(longitude),
        "usgs_mag": str(usgs_mag),
    }


class TestMatchEvents:
    """Tests use Kermadec record: cen_lat=-29.25, cen_lon=-176.96, cen_depth=47.8.
    Centroid time ≈ 1976-01-01T01:29:53.4Z (ref + 13.8 s).
    Mw from M0 = 9.560e26 dyne-cm → Mw ≈ 7.29.
    """

    _CEN_TIME = _utc(1976, 1, 1, 1, 29, 53, 400000)
    _KERMADEC_MW = pytest.approx((2.0 / 3.0) * (26 + 0.9805) - 10.7, abs=0.01)

    def _gcmt_recs(self, tmp_path):
        path = _write_ndk(tmp_path, _NDK_KERMADEC)
        return parse_ndk_records(path)

    def test_matched_event_has_proximity_confidence(self, tmp_path):
        ev = _make_iscgem("eq1", "1976-01-01T01:29:53Z", -29.25, -176.96, 7.29)
        recs = self._gcmt_recs(tmp_path)
        results = match_events([ev], recs, time_tol_s=60, dist_km=50, mag_tol=0.5)
        assert results[0]["match_confidence"] == MATCH_PROXIMITY

    def test_matched_event_gcmt_id(self, tmp_path):
        ev = _make_iscgem("eq1", "1976-01-01T01:29:53Z", -29.25, -176.96, 7.29)
        recs = self._gcmt_recs(tmp_path)
        results = match_events([ev], recs, time_tol_s=60, dist_km=50, mag_tol=0.5)
        assert results[0]["gcmt_id"] == "M010176A"

    def test_matched_event_mechanism(self, tmp_path):
        ev = _make_iscgem("eq1", "1976-01-01T01:29:53Z", -29.25, -176.96, 7.29)
        recs = self._gcmt_recs(tmp_path)
        results = match_events([ev], recs, time_tol_s=60, dist_km=50, mag_tol=0.5)
        assert results[0]["mechanism"] == THRUST

    def test_matched_event_rake_strike_dip(self, tmp_path):
        ev = _make_iscgem("eq1", "1976-01-01T01:29:53Z", -29.25, -176.96, 7.29)
        recs = self._gcmt_recs(tmp_path)
        results = match_events([ev], recs, time_tol_s=60, dist_km=50, mag_tol=0.5)
        assert results[0]["rake"] == 93
        assert results[0]["strike"] == 202
        assert results[0]["dip"] == 30

    def test_matched_event_centroid_depth(self, tmp_path):
        ev = _make_iscgem("eq1", "1976-01-01T01:29:53Z", -29.25, -176.96, 7.29)
        recs = self._gcmt_recs(tmp_path)
        results = match_events([ev], recs, time_tol_s=60, dist_km=50, mag_tol=0.5)
        assert float(results[0]["centroid_depth"]) == pytest.approx(47.8)

    def test_unmatched_when_time_outside_tolerance(self, tmp_path):
        ev = _make_iscgem("eq1", "1976-01-01T02:30:00Z", -29.25, -176.96, 7.29)
        recs = self._gcmt_recs(tmp_path)
        results = match_events([ev], recs, time_tol_s=60, dist_km=50, mag_tol=0.5)
        assert results[0]["match_confidence"] == MATCH_NULL

    def test_unmatched_when_distance_outside_tolerance(self, tmp_path):
        # ~500 km away from Kermadec centroid
        ev = _make_iscgem("eq1", "1976-01-01T01:29:53Z", -25.0, -176.96, 7.29)
        recs = self._gcmt_recs(tmp_path)
        results = match_events([ev], recs, time_tol_s=60, dist_km=50, mag_tol=0.5)
        assert results[0]["match_confidence"] == MATCH_NULL

    def test_unmatched_when_magnitude_outside_tolerance(self, tmp_path):
        ev = _make_iscgem("eq1", "1976-01-01T01:29:53Z", -29.25, -176.96, 5.0)
        recs = self._gcmt_recs(tmp_path)
        results = match_events([ev], recs, time_tol_s=60, dist_km=50, mag_tol=0.3)
        assert results[0]["match_confidence"] == MATCH_NULL

    def test_unmatched_event_has_empty_gcmt_columns(self, tmp_path):
        ev = _make_iscgem("eq1", "2000-01-01T00:00:00Z", 0.0, 0.0, 6.0)
        recs = self._gcmt_recs(tmp_path)
        results = match_events([ev], recs)
        for col in APPEND_FIELDNAMES:
            if col != "match_confidence":
                assert results[0][col] == ""

    def test_original_columns_preserved(self, tmp_path):
        ev = _make_iscgem("eq1", "1976-01-01T01:29:53Z", -29.25, -176.96, 7.29)
        recs = self._gcmt_recs(tmp_path)
        results = match_events([ev], recs, time_tol_s=60, dist_km=50, mag_tol=0.5)
        assert results[0]["usgs_id"] == "eq1"

    def test_empty_catalog(self, tmp_path):
        recs = self._gcmt_recs(tmp_path)
        results = match_events([], recs)
        assert results == []

    def test_empty_gcmt(self):
        ev = _make_iscgem("eq1", "1976-01-01T01:29:53Z", -29.25, -176.96, 7.29)
        results = match_events([ev], [])
        assert results[0]["match_confidence"] == MATCH_NULL

    def test_row_count_matches_input(self, tmp_path):
        events = [
            _make_iscgem(f"eq{i}", "2000-01-01T00:00:00Z", float(i), 0.0, 6.0)
            for i in range(5)
        ]
        recs = self._gcmt_recs(tmp_path)
        results = match_events(events, recs)
        assert len(results) == 5


# ---------------------------------------------------------------------------
# _gcmt_mw helper
# ---------------------------------------------------------------------------

class TestGcmtMw:
    def test_known_value(self):
        # M0 = 10^25 dyne-cm → Mw = (2/3)*25 - 10.7 = 16.67 - 10.7 = 5.97
        assert _gcmt_mw(1e25) == pytest.approx(5.967, abs=0.01)

    def test_zero_returns_zero(self):
        assert _gcmt_mw(0.0) == 0.0

    def test_negative_returns_zero(self):
        assert _gcmt_mw(-1.0) == 0.0
