"""Tests for nornir_urd.pb2002 module."""

import csv
import textwrap

import pytest

from nornir_urd.pb2002 import OUTPUT_FIELDNAMES, parse_pb2002_steps, write_pb2002_types


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_LINE = (
    "1 AF-AN 19.162 -72.209 19.162 -72.209 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 :CTF"
)

_VALID_LINE_COLON_PAIR = (
    "2 :SO-AN 19.162 -72.209 20.000 -73.000 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 :SUB"
)

_VALID_LINES_CONTENT = textwrap.dedent("""\
    1 AF-AN 19.162 -72.209 19.162 -72.209 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 :CTF
    2 SO-AN 20.000 -73.000 21.000 -74.000 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 :OSR
""")


@pytest.fixture
def steps_file(tmp_path):
    """Write a minimal valid pb2002_steps.dat and return the path."""
    p = tmp_path / "pb2002_steps.dat"
    p.write_text(_VALID_LINES_CONTENT)
    return str(p)


# ---------------------------------------------------------------------------
# parse_pb2002_steps
# ---------------------------------------------------------------------------

class TestParsePb2002Steps:
    def test_returns_list_of_dicts(self, steps_file):
        rows = parse_pb2002_steps(steps_file)
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows)

    def test_correct_row_count(self, steps_file):
        rows = parse_pb2002_steps(steps_file)
        assert len(rows) == 2

    def test_fieldnames_present(self, steps_file):
        rows = parse_pb2002_steps(steps_file)
        for row in rows:
            for field in OUTPUT_FIELDNAMES:
                assert field in row

    def test_plate_pair_split(self, steps_file):
        rows = parse_pb2002_steps(steps_file)
        assert rows[0]["plate_a"] == "AF"
        assert rows[0]["plate_b"] == "AN"

    def test_type_code_stripped(self, steps_file):
        rows = parse_pb2002_steps(steps_file)
        assert rows[0]["boundary_type_code"] == "CTF"

    def test_type_label_populated(self, steps_file):
        rows = parse_pb2002_steps(steps_file)
        assert rows[0]["boundary_type_label"] == "Continental transform fault"
        assert rows[1]["boundary_type_label"] == "Oceanic spreading ridge"

    def test_midpoint_coordinates(self, tmp_path):
        """Midpoint lon/lat should be the mean of start and end coordinates."""
        content = "1 AF-AN 10.0 20.0 20.0 40.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 :CTF\n"
        p = tmp_path / "steps.dat"
        p.write_text(content)
        rows = parse_pb2002_steps(str(p))
        assert len(rows) == 1
        assert rows[0]["lon"] == pytest.approx(15.0)
        assert rows[0]["lat"] == pytest.approx(30.0)

    def test_segment_id_is_integer(self, steps_file):
        rows = parse_pb2002_steps(steps_file)
        assert rows[0]["segment_id"] == 1

    def test_colon_prefix_on_plate_pair_stripped(self, tmp_path):
        """Leading colon on plate pair field should be stripped."""
        content = "1 :AF-AN 10.0 20.0 20.0 40.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 :CTF\n"
        p = tmp_path / "steps.dat"
        p.write_text(content)
        rows = parse_pb2002_steps(str(p))
        assert rows[0]["plate_a"] == "AF"
        assert rows[0]["plate_b"] == "AN"

    def test_unknown_type_code_skipped(self, tmp_path):
        content = "1 AF-AN 10.0 20.0 10.0 20.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 :XXX\n"
        p = tmp_path / "steps.dat"
        p.write_text(content)
        rows = parse_pb2002_steps(str(p))
        assert len(rows) == 0

    def test_comment_lines_skipped(self, tmp_path):
        content = (
            "# This is a comment\n"
            "1 AF-AN 10.0 20.0 10.0 20.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 :CTF\n"
        )
        p = tmp_path / "steps.dat"
        p.write_text(content)
        rows = parse_pb2002_steps(str(p))
        assert len(rows) == 1

    def test_short_rows_skipped(self, tmp_path):
        content = "1 AF-AN 10.0 20.0\n"
        p = tmp_path / "steps.dat"
        p.write_text(content)
        rows = parse_pb2002_steps(str(p))
        assert len(rows) == 0

    def test_empty_file(self, tmp_path):
        p = tmp_path / "steps.dat"
        p.write_text("")
        rows = parse_pb2002_steps(str(p))
        assert rows == []

    def test_all_boundary_type_codes_recognised(self, tmp_path):
        codes = ["CTF", "CRB", "CCB", "OSR", "OTF", "OCB", "SUB"]
        lines = "\n".join(
            f"{i+1} AF-AN 10.0 20.0 10.0 20.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 :{code}"
            for i, code in enumerate(codes)
        )
        p = tmp_path / "steps.dat"
        p.write_text(lines + "\n")
        rows = parse_pb2002_steps(str(p))
        assert len(rows) == len(codes)
        parsed_codes = {r["boundary_type_code"] for r in rows}
        assert parsed_codes == set(codes)


# ---------------------------------------------------------------------------
# write_pb2002_types
# ---------------------------------------------------------------------------

class TestWritePb2002Types:
    def test_writes_csv_with_correct_header(self, tmp_path, steps_file):
        rows = parse_pb2002_steps(steps_file)
        out = tmp_path / "types.csv"
        write_pb2002_types(rows, str(out))
        with open(out, newline="") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == OUTPUT_FIELDNAMES

    def test_row_count_matches(self, tmp_path, steps_file):
        rows = parse_pb2002_steps(steps_file)
        out = tmp_path / "types.csv"
        write_pb2002_types(rows, str(out))
        with open(out, newline="") as f:
            written = list(csv.DictReader(f))
        assert len(written) == len(rows)
