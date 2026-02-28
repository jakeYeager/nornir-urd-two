"""Ocean/continent classification for earthquake events.

Classifies each event as ``oceanic``, ``continental``, or ``transitional``
based on its minimum Haversine distance to the nearest coastline vertex.

Classification scheme
---------------------
  oceanic       distance > oceanic_km (default 200 km) from nearest coastline
  continental   distance <= coastal_km (default 50 km) from nearest coastline
  transitional  between coastal_km and oceanic_km

Three data sources are supported via the ``--method`` CLI flag:

  ne      Natural Earth coastline vertex CSV (default, Option B)
          Pure stdlib Haversine scan. Requires a pre-computed ``lon,lat``
          CSV derived from the Natural Earth ne_10m_coastline shapefile.
  gshhg   GSHHG coastline vertex CSV (higher resolution, same algorithm)
  pb2002  PB2002 plate boundary midpoints as a coarse coastline proxy
          (Option C). Lower accuracy; no external coastline data needed
          beyond ``lib/pb2002_types.csv``.

# Option A (shapely + shapefile) would provide higher spatial accuracy
# through proper segment-to-point distance queries rather than vertex
# sampling.  Not implemented here due to dependency policy; this comment
# is the designated future upgrade path reference.
"""

from __future__ import annotations

import csv

from .decluster import haversine_km

OCEANIC = "oceanic"
CONTINENTAL = "continental"
TRANSITIONAL = "transitional"

OUTPUT_FIELDNAMES = ["usgs_id", "ocean_class", "dist_to_coast_km"]


def load_coastline_vertices(path: str) -> list[tuple[float, float]]:
    """Load a ``lon,lat`` CSV into a list of ``(lon, lat)`` tuples.

    The file may have a header row; non-numeric rows are silently skipped.
    """
    vertices: list[tuple[float, float]] = []
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            try:
                vertices.append((float(row[0]), float(row[1])))
            except ValueError:
                continue  # skip header or malformed rows
    return vertices


def load_pb2002_vertices(path: str) -> list[tuple[float, float]]:
    """Load ``(lon, lat)`` tuples from a ``lib/pb2002_types.csv`` file."""
    vertices: list[tuple[float, float]] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                vertices.append((float(row["lon"]), float(row["lat"])))
            except (ValueError, KeyError):
                continue
    return vertices


def dist_to_nearest_vertex(
    lat: float,
    lon: float,
    vertices: list[tuple[float, float]],
) -> float:
    """Return the minimum Haversine distance (km) from ``(lat, lon)`` to any vertex."""
    min_dist = float("inf")
    for v_lon, v_lat in vertices:
        d = haversine_km(lat, lon, v_lat, v_lon)
        if d < min_dist:
            min_dist = d
    return min_dist


def classify_distance(dist_km: float, oceanic_km: float, coastal_km: float) -> str:
    """Return the ocean class label for a given distance from the coastline."""
    if dist_km > oceanic_km:
        return OCEANIC
    if dist_km <= coastal_km:
        return CONTINENTAL
    return TRANSITIONAL


def classify_events(
    events: list[dict],
    vertices: list[tuple[float, float]],
    oceanic_km: float = 200.0,
    coastal_km: float = 50.0,
) -> list[dict]:
    """Classify each event by distance to nearest coastline vertex.

    Each event dict must contain at minimum ``usgs_id``, ``latitude``,
    and ``longitude``.

    Returns a list of dicts with schema:
        usgs_id, ocean_class, dist_to_coast_km
    """
    results: list[dict] = []
    for event in events:
        lat = float(event["latitude"])
        lon = float(event["longitude"])
        dist = dist_to_nearest_vertex(lat, lon, vertices)
        results.append(
            {
                "usgs_id": event["usgs_id"],
                "ocean_class": classify_distance(dist, oceanic_km, coastal_km),
                "dist_to_coast_km": round(dist, 3),
            }
        )
    return results
