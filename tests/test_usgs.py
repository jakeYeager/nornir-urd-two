"""Tests for nornir_urd.usgs USGS API client."""

from datetime import date
from unittest.mock import patch

import httpx
import pytest

from nornir_urd.usgs import _truncate_time, fetch_earthquakes

SAMPLE_CSV = """\
time,latitude,longitude,depth,mag,magType,nst,gap,dmin,rms,net,id,updated,place,type,horizontalError,depthError,magError,magNst,status,locationSource,magSource
2026-02-12T13:34:31.114Z,35.6762,139.6503,25.0,6.3,mww,,25,0.847,0.92,us,us7000abc1,2026-02-12T14:00:00.000Z,"10 km NW of Tokyo, Japan",earthquake,,,,,reviewed,us,us
2026-02-10T08:15:00.000Z,-33.4489,-70.6693,50.0,6.7,mww,,30,1.2,1.1,us,us7000abc2,2026-02-10T09:00:00.000Z,"Santiago, Chile",earthquake,,,,,reviewed,us,us
"""

SAMPLE_CSV_EMPTY_DEPTH = """\
time,latitude,longitude,depth,mag,magType,nst,gap,dmin,rms,net,id,updated,place,type,horizontalError,depthError,magError,magNst,status,locationSource,magSource
2026-02-12T13:34:31.114Z,35.6762,139.6503,,6.3,mww,,25,0.847,0.92,us,us7000abc1,2026-02-12T14:00:00.000Z,"10 km NW of Tokyo, Japan",earthquake,,,,,reviewed,us,us
"""


def _mock_response(text: str, status_code: int = 200) -> httpx.Response:
    """Create a mock httpx.Response."""
    response = httpx.Response(
        status_code=status_code,
        text=text,
        request=httpx.Request("GET", "https://example.com"),
    )
    return response


class TestTruncateTime:
    def test_with_milliseconds(self):
        assert _truncate_time("2026-02-12T13:34:31.114Z") == "2026-02-12T13:34:31Z"

    def test_already_truncated(self):
        assert _truncate_time("2026-02-12T13:34:31Z") == "2026-02-12T13:34:31Z"

    def test_no_z_suffix(self):
        assert _truncate_time("2026-02-12T13:34:31.114") == "2026-02-12T13:34:31.114"


class TestFetchEarthquakes:
    @patch("nornir_urd.usgs.httpx.get")
    def test_parses_fields(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_CSV)

        events = fetch_earthquakes(
            start=date(2026, 2, 9),
            end=date(2026, 2, 13),
        )

        assert len(events) == 2
        assert events[0]["usgs_id"] == "us7000abc1"
        assert events[0]["usgs_mag"] == 6.3
        assert events[0]["latitude"] == 35.6762
        assert events[0]["longitude"] == 139.6503
        assert events[0]["depth"] == 25.0
        assert events[1]["usgs_id"] == "us7000abc2"
        assert events[1]["usgs_mag"] == 6.7
        assert events[1]["latitude"] == -33.4489
        assert events[1]["longitude"] == -70.6693
        assert events[1]["depth"] == 50.0

    @patch("nornir_urd.usgs.httpx.get")
    def test_time_truncated(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_CSV)

        events = fetch_earthquakes(
            start=date(2026, 2, 9),
            end=date(2026, 2, 13),
        )

        assert events[0]["event_at"] == "2026-02-12T13:34:31Z"
        assert events[1]["event_at"] == "2026-02-10T08:15:00Z"

    @patch("nornir_urd.usgs.httpx.get")
    def test_optional_params_included_when_set(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_CSV)

        fetch_earthquakes(
            start=date(2026, 2, 9),
            end=date(2026, 2, 13),
            min_lat=-10.0,
            max_lat=10.0,
        )

        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["minlatitude"] == -10.0
        assert params["maxlatitude"] == 10.0
        assert "minlongitude" not in params
        assert "maxlongitude" not in params

    @patch("nornir_urd.usgs.httpx.get")
    def test_optional_params_omitted_by_default(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_CSV)

        fetch_earthquakes(
            start=date(2026, 2, 9),
            end=date(2026, 2, 13),
        )

        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        for key in ("minlatitude", "maxlatitude", "minlongitude", "maxlongitude"):
            assert key not in params

    @patch("nornir_urd.usgs.httpx.get")
    def test_empty_depth_defaults_to_zero(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_CSV_EMPTY_DEPTH)

        events = fetch_earthquakes(
            start=date(2026, 2, 9),
            end=date(2026, 2, 13),
        )

        assert len(events) == 1
        assert events[0]["depth"] == 0.0

    @patch("nornir_urd.usgs.httpx.get")
    def test_catalog_included_by_default(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_CSV)

        fetch_earthquakes(
            start=date(2026, 2, 9),
            end=date(2026, 2, 13),
        )

        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["catalog"] == "iscgem"

    @patch("nornir_urd.usgs.httpx.get")
    def test_catalog_omitted_when_none(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_CSV)

        fetch_earthquakes(
            start=date(2026, 2, 9),
            end=date(2026, 2, 13),
            catalog=None,
        )

        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert "catalog" not in params
