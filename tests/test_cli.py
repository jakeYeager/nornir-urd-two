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
        "latitude": 35.6762,
        "longitude": 139.6503,
        "depth": 25.0,
    },
    {
        "usgs_id": "us7000abc2",
        "usgs_mag": 6.7,
        "event_at": "2026-02-10T08:15:00Z",
        "latitude": -33.4489,
        "longitude": -70.6693,
        "depth": 50.0,
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

    def test_catalog_default(self):
        parser = build_parser()
        args = parser.parse_args(["collect", "--output", "out.csv"])
        assert args.catalog == "iscgem"

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
        assert header == "usgs_id,usgs_mag,event_at,solaration_year,solar_secs,lunar_secs,midnight_secs,latitude,longitude,depth"
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
        # Verify structure: usgs_id, usgs_mag, event_at, solaration_year, solar_secs, lunar_secs, midnight_secs, latitude, longitude, depth
        assert row1[0] == "us7000abc1"
        assert row1[1] == "6.3"
        assert row1[2] == "2026-02-12T13:34:31Z"
        assert row1[3] == "2026"  # solaration_year
        # solar_secs, lunar_secs, midnight_secs should be integers
        assert int(row1[4]) > 0
        assert int(row1[5]) > 0
        assert int(row1[6]) > 0
        assert row1[7] == "35.6762"
        assert row1[8] == "139.6503"
        assert row1[9] == "25.0"

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


DECLUSTER_CSV = """\
usgs_id,usgs_mag,event_at,latitude,longitude,depth
mainshock,7.0,2026-01-15T12:00:00Z,35.0,139.0,10.0
aftershock,5.5,2026-01-15T14:00:00Z,35.1,139.1,15.0
independent,6.5,2026-06-01T08:00:00Z,-33.0,-70.0,30.0
"""


class TestDeclusterCommand:
    def test_splits_catalog(self, tmp_path):
        infile = tmp_path / "input.csv"
        infile.write_text(DECLUSTER_CSV)
        mainfile = tmp_path / "mainshocks.csv"
        afterfile = tmp_path / "aftershocks.csv"

        main([
            "decluster",
            "--input", str(infile),
            "--mainshocks", str(mainfile),
            "--aftershocks", str(afterfile),
        ])

        main_lines = mainfile.read_text().strip().split("\n")
        after_lines = afterfile.read_text().strip().split("\n")
        # Header + 2 mainshocks (mainshock + independent)
        assert len(main_lines) == 3
        # Header + 1 aftershock
        assert len(after_lines) == 2
        assert "aftershock" in after_lines[1]

    def test_preserves_all_columns(self, tmp_path):
        infile = tmp_path / "input.csv"
        infile.write_text(DECLUSTER_CSV)
        mainfile = tmp_path / "mainshocks.csv"
        afterfile = tmp_path / "aftershocks.csv"

        main([
            "decluster",
            "--input", str(infile),
            "--mainshocks", str(mainfile),
            "--aftershocks", str(afterfile),
        ])

        header = mainfile.read_text().strip().split("\n")[0]
        assert header == "usgs_id,usgs_mag,event_at,latitude,longitude,depth"

    def test_missing_columns_exits(self, tmp_path):
        infile = tmp_path / "bad.csv"
        infile.write_text("usgs_id,usgs_mag\nev1,6.0\n")
        mainfile = tmp_path / "m.csv"
        afterfile = tmp_path / "a.csv"

        with pytest.raises(SystemExit):
            main([
                "decluster",
                "--input", str(infile),
                "--mainshocks", str(mainfile),
                "--aftershocks", str(afterfile),
            ])
