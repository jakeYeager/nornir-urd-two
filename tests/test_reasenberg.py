"""Tests for nornir_urd.reasenberg module."""

from nornir_urd.reasenberg import _r_int, _tau, decluster_reasenberg


class TestRInt:
    def test_increases_with_magnitude(self):
        """Interaction radius grows with magnitude."""
        assert _r_int(5.0, 10.0) < _r_int(6.0, 10.0) < _r_int(7.0, 10.0)

    def test_scales_with_rfact(self):
        """Doubling rfact doubles the radius."""
        r1 = _r_int(6.0, 10.0)
        r2 = _r_int(6.0, 20.0)
        assert abs(r2 - 2 * r1) < 1e-9

    def test_positive_for_any_magnitude(self):
        for m in [2.0, 4.0, 6.0, 8.0]:
            assert _r_int(m, 10.0) > 0


class TestTau:
    def test_clamped_to_tau_min_for_large_mmax(self):
        """For large M (many expected aftershocks) τ collapses to tau_min."""
        tau = _tau(mmax=7.0, xmeff=1.5, p=0.95, tau_min=1.0, tau_max=10.0)
        assert tau == 1.0

    def test_clamped_to_tau_max_for_small_mmax(self):
        """For mmax well below xmeff, very few aftershocks expected, τ hits tau_max.

        mmax=0.5, xmeff=1.5: λ = 10^-1 = 0.1; raw τ ≈ 30 days → clamped to 10.
        """
        tau = _tau(mmax=0.5, xmeff=1.5, p=0.95, tau_min=1.0, tau_max=10.0)
        assert tau == 10.0

    def test_within_bounds(self):
        for mmax in [2.0, 4.0, 6.0, 8.0]:
            tau = _tau(mmax=mmax, xmeff=1.5, p=0.95, tau_min=1.0, tau_max=10.0)
            assert 1.0 <= tau <= 10.0

    def test_overflow_guard(self):
        """Very large mmax should not raise and should return tau_min."""
        tau = _tau(mmax=500.0, xmeff=1.5, p=0.95, tau_min=1.0, tau_max=10.0)
        assert tau == 1.0


class TestDeclustersReasenberg:
    _MAINSHOCK = {
        "usgs_id": "main",
        "usgs_mag": 7.0,
        "event_at": "2020-06-01T00:00:00Z",
        "latitude": 35.0,
        "longitude": 139.0,
    }
    _AFTERSHOCK = {
        "usgs_id": "after",
        "usgs_mag": 5.5,
        "event_at": "2020-06-01T06:00:00Z",  # 6 h later, ~14 km away
        "latitude": 35.1,
        "longitude": 139.1,
    }
    _REMOTE = {
        "usgs_id": "remote",
        "usgs_mag": 6.0,
        "event_at": "2020-06-01T03:00:00Z",
        "latitude": -33.0,
        "longitude": -70.0,  # Chile — thousands of km away
    }

    def test_empty_catalog(self):
        assert decluster_reasenberg([]) == ([], [])

    def test_single_event_is_mainshock(self):
        main, after = decluster_reasenberg([self._MAINSHOCK])
        assert len(main) == 1
        assert len(after) == 0
        assert main[0]["usgs_id"] == "main"

    def test_close_aftershock_flagged(self):
        """A smaller event close in space and time joins the mainshock cluster."""
        main, after = decluster_reasenberg([self._MAINSHOCK, self._AFTERSHOCK])
        assert len(main) == 1
        assert main[0]["usgs_id"] == "main"
        assert len(after) == 1
        assert after[0]["usgs_id"] == "after"

    def test_remote_event_not_flagged(self):
        """An event thousands of km away is not clustered with the mainshock."""
        main, after = decluster_reasenberg([self._MAINSHOCK, self._REMOTE])
        assert len(main) == 2
        assert len(after) == 0

    def test_temporally_distant_not_flagged(self):
        """An event beyond tau_max days after the mainshock is not clustered."""
        late_event = {
            "usgs_id": "late",
            "usgs_mag": 5.5,
            "event_at": "2020-06-30T00:00:00Z",  # 29 days later — beyond tau_max=10
            "latitude": 35.1,
            "longitude": 139.1,
        }
        main, after = decluster_reasenberg(
            [self._MAINSHOCK, late_event], tau_max=10.0
        )
        assert len(main) == 2
        assert len(after) == 0

    def test_largest_magnitude_is_mainshock(self):
        """Within a cluster the highest-magnitude event is the mainshock."""
        small_first = {
            "usgs_id": "small",
            "usgs_mag": 5.0,
            "event_at": "2020-06-01T00:00:00Z",
            "latitude": 35.0,
            "longitude": 139.0,
        }
        large_later = {
            "usgs_id": "large",
            "usgs_mag": 7.0,
            "event_at": "2020-06-01T01:00:00Z",  # 1 h later, same location
            "latitude": 35.0,
            "longitude": 139.0,
        }
        main, after = decluster_reasenberg([small_first, large_later])
        assert len(main) == 1
        assert main[0]["usgs_id"] == "large"
        assert len(after) == 1
        assert after[0]["usgs_id"] == "small"

    def test_preserves_extra_keys(self):
        event = dict(self._MAINSHOCK, depth=25.0, custom="hello")
        main, _ = decluster_reasenberg([event])
        assert main[0]["depth"] == 25.0
        assert main[0]["custom"] == "hello"

    def test_custom_rfact_excludes_nearby_event(self):
        """With rfact=0.001 the interaction radius is tiny; no clustering occurs."""
        main, after = decluster_reasenberg(
            [self._MAINSHOCK, self._AFTERSHOCK], rfact=0.001
        )
        assert len(main) == 2
        assert len(after) == 0
