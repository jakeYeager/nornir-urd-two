"""PB2002 plate boundary type parser.

Parses ``pb2002_steps.dat`` from Peter Bird (2003) "An updated digital model
of plate boundaries" (G-cubed, 4(3), 1027) into a structured CSV lookup table
that maps each boundary step to its plate pair, boundary type code, and
midpoint coordinates.

File format (space-delimited, no header line)
---------------------------------------------
Each row has at least 15 whitespace-delimited fields:

  col  1  step_id          — sequential integer
  col  2  plate_pair       — e.g. ``AF-AN`` (leading colon stripped)
  col  3  start_lon        — longitude of step start point (°E)
  col  4  start_lat        — latitude of step start point (°N)
  col  5  end_lon          — longitude of step end point (°E)
  col  6  end_lat          — latitude of step end point (°N)
  cols 7–14               — velocity / depth / reference fields (not used)
  col 15  boundary_type    — 3-letter type code (leading colon stripped)

The midpoint of each step is computed as the arithmetic mean of start and
end coordinates.

Boundary type codes (Bird 2003, Table 1)
-----------------------------------------
  CTF  Continental transform fault
  CRB  Continental rift boundary
  CCB  Continental convergent boundary
  OSR  Oceanic spreading ridge
  OTF  Oceanic transform fault
  OCB  Oceanic convergent boundary
  SUB  Subduction zone
"""

from __future__ import annotations

import csv

_TYPE_LABELS: dict[str, str] = {
    "CTF": "Continental transform fault",
    "CRB": "Continental rift boundary",
    "CCB": "Continental convergent boundary",
    "OSR": "Oceanic spreading ridge",
    "OTF": "Oceanic transform fault",
    "OCB": "Oceanic convergent boundary",
    "SUB": "Subduction zone",
}

OUTPUT_FIELDNAMES = [
    "segment_id",
    "plate_a",
    "plate_b",
    "boundary_type_code",
    "boundary_type_label",
    "lon",
    "lat",
]


def parse_pb2002_steps(path: str) -> list[dict]:
    """Parse ``pb2002_steps.dat`` and return a list of boundary segment dicts.

    Each dict contains:
        segment_id          -- original step integer ID
        plate_a             -- first plate abbreviation (e.g. ``AF``)
        plate_b             -- second plate abbreviation (e.g. ``AN``)
        boundary_type_code  -- 3-letter code (CTF, CRB, CCB, OSR, OTF, OCB, SUB)
        boundary_type_label -- human-readable description
        lon                 -- midpoint longitude (°E)
        lat                 -- midpoint latitude (°N)

    Rows with unrecognised type codes or fewer than 15 fields are skipped.
    """
    rows: list[dict] = []

    with open(path) as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) < 15:
                continue

            try:
                step_id = int(parts[0])
                plate_pair = parts[1].lstrip(":")
                start_lon = float(parts[2])
                start_lat = float(parts[3])
                end_lon = float(parts[4])
                end_lat = float(parts[5])
            except (ValueError, IndexError):
                continue

            type_code = parts[14].lstrip(":")
            if type_code not in _TYPE_LABELS:
                continue

            # Split plate pair: "AF-AN" → plate_a="AF", plate_b="AN"
            if "-" in plate_pair:
                plate_a, plate_b = plate_pair.split("-", 1)
            else:
                plate_a, plate_b = plate_pair, ""

            mid_lon = (start_lon + end_lon) / 2.0
            mid_lat = (start_lat + end_lat) / 2.0

            rows.append(
                {
                    "segment_id": step_id,
                    "plate_a": plate_a,
                    "plate_b": plate_b,
                    "boundary_type_code": type_code,
                    "boundary_type_label": _TYPE_LABELS[type_code],
                    "lon": round(mid_lon, 5),
                    "lat": round(mid_lat, 5),
                }
            )

    return rows


def write_pb2002_types(rows: list[dict], output_path: str) -> None:
    """Write parsed PB2002 boundary segments to a CSV file."""
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
