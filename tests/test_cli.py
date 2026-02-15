"""Tests for nornir_urd.cli module."""

from datetime import date
from unittest.mock import patch

import pytest

from nornir_urd.cli import main, build_parser

FIXTURE_EVENTS = [
    {
        "usgs_id": "us7000abc1",
        "usgs_mag": 6.3,
        "event_at": "2026-02-12T13:34:31Z",
        "longitude": 139.6503,
    },
    {
        "usgs_id": "us7000abc2",
        "usgs_mag": 6.7,
        "event_at": "2026-02-10T08:15:00Z",
        "longitude": -70.6693,
    },
]


class TestArgDefaults:
    def test_default_dates(self):
        """Start defaults to today-5, end defaults to today."""
        parser = build_parser()
        args = parser.parse_args(["collect", "--output", "out.csv"])
        assert args.start is None
        assert args.end is None
        assert args.min_mag == 6.0
        assert args.max_mag == 6.9

    def test_explicit_dates(self):
        parser = build_parser()
        args = parser.parse_args([
            "collect",
            "--start", "2026-01-01",
            "--end", "2026-01-31",
            "--output", "out.csv",
        ])
        assert args.start == date(2026, 1, 1)
        assert args.end == date(2026, 1, 31)


class TestCollectCommand:
    @patch("nornir_urd.cli.fetch_earthquakes", return_value=FIXTURE_EVENTS)
    def test_writes_csv(self, mock_fetch, tmp_path):
        outfile = tmp_path / "output.csv"
        main([
            "collect",
            "--start", "2026-02-09",
            "--end", "2026-02-13",
            "--output", str(outfile),
        ])

        assert outfile.exists()
        lines = outfile.read_text().strip().split("\n")
        header = lines[0]
        assert header == "usgs_id,usgs_mag,event_at,solaration_year,solar_secs,lunar_secs,midnight_secs,longitude"
        # Two data rows
        assert len(lines) == 3

    @patch("nornir_urd.cli.fetch_earthquakes", return_value=FIXTURE_EVENTS)
    def test_csv_values(self, mock_fetch, tmp_path):
        outfile = tmp_path / "output.csv"
        main([
            "collect",
            "--start", "2026-02-09",
            "--end", "2026-02-13",
            "--output", str(outfile),
        ])

        lines = outfile.read_text().strip().split("\n")
        row1 = lines[1].split(",")
        # Verify structure: usgs_id, usgs_mag, event_at, solaration_year, solar_secs, lunar_secs, midnight_secs, longitude
        assert row1[0] == "us7000abc1"
        assert row1[1] == "6.3"
        assert row1[2] == "2026-02-12T13:34:31Z"
        assert row1[3] == "2026"  # solaration_year
        # solar_secs, lunar_secs, midnight_secs should be integers
        assert int(row1[4]) > 0
        assert int(row1[5]) > 0
        assert int(row1[6]) > 0
        assert row1[7] == "139.6503"

    @patch("nornir_urd.cli.fetch_earthquakes", return_value=[])
    def test_empty_results(self, mock_fetch, tmp_path):
        outfile = tmp_path / "output.csv"
        main([
            "collect",
            "--start", "2026-02-09",
            "--end", "2026-02-13",
            "--output", str(outfile),
        ])

        lines = outfile.read_text().strip().split("\n")
        assert len(lines) == 1  # Header only
