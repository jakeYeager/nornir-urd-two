"""GCMT NDK file parser, event matcher, and focal mechanism classifier.

NDK file format (5 lines per event)
-------------------------------------
Line 1  Hypocenter reference:
        {catalog}  {YYYY/MM/DD}  {HH:MM:SS.S}  {lat}  {lon}  {depth}
        {mb}  {Ms}  {region}

Line 2  CMT header:
        {gcmt_id}  {data_used_codes}  CMT: ...

Line 3  Centroid parameters:
        CENTROID:  {time_shift}  {σ}  {cen_lat}  {σ}  {cen_lon}  {σ}
        {cen_depth}  {σ}  {depth_type}  {timestamp}

Line 4  Moment tensor (dyne-cm, units 10^exponent):
        {exponent}  {Mrr} {σ}  {Mtt} {σ}  {Mpp} {σ}
        {Mrt} {σ}  {Mrp} {σ}  {Mtp} {σ}

Line 5  Principal axes and best-fitting nodal planes:
        {version}  {T_val} {T_plunge} {T_az}
        {N_val} {N_plunge} {N_az}  {P_val} {P_plunge} {P_az}
        {scalar_moment_mantissa}
        {NP1_strike} {NP1_dip} {NP1_rake}
        {NP2_strike} {NP2_dip} {NP2_rake}

Scalar moment M0 (dyne-cm) = scalar_moment_mantissa × 10^exponent (Line 4 exponent).
Mw = (2/3) × log10(M0) − 10.7   (M0 in dyne-cm).
"""

from __future__ import annotations

import bisect
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .decluster import haversine_km

# ---------------------------------------------------------------------------
# Mechanism constants
# ---------------------------------------------------------------------------
THRUST = "thrust"
NORMAL = "normal"
STRIKE_SLIP = "strike_slip"
OBLIQUE = "oblique"

# Match-confidence labels
MATCH_PROXIMITY = "proximity"
MATCH_NULL = "null"

# Columns appended to input CSV by focal-join
APPEND_FIELDNAMES = [
    "gcmt_id",
    "mechanism",
    "rake",
    "strike",
    "dip",
    "scalar_moment",
    "centroid_depth",
    "match_confidence",
]


# ---------------------------------------------------------------------------
# Mechanism classification
# ---------------------------------------------------------------------------

def classify_mechanism(rake: float) -> str:
    """Classify focal mechanism from rake angle (degrees).

    Thresholds follow Phase 3 specification (06_phases.md):
      thrust:      rake ∈ [45°, 135°]
      normal:      rake ∈ [−135°, −45°]
      strike_slip: rake ∈ (−45°, 45°) ∪ (135°, 180°] ∪ [−180°, −135°)
      oblique:     rake exactly at a quadrant boundary (rare in practice)
    """
    # Normalise to (−180, 180]
    r = ((rake + 180.0) % 360.0) - 180.0
    if 45.0 <= r <= 135.0:
        return THRUST
    if -135.0 <= r <= -45.0:
        return NORMAL
    if -45.0 < r < 45.0 or 135.0 < r <= 180.0 or -180.0 < r < -135.0:
        return STRIKE_SLIP
    return OBLIQUE  # r == ±180 or exact boundary (edge case)


# ---------------------------------------------------------------------------
# NDK parsing
# ---------------------------------------------------------------------------

def _parse_ndk_dt(date_str: str, time_str: str) -> datetime:
    """Parse NDK ``YYYY/MM/DD`` + ``HH:MM:SS.S[S]`` into a UTC datetime."""
    dt_str = f"{date_str} {time_str}"
    for fmt in ("%Y/%m/%d %H:%M:%S.%f", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(dt_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse NDK datetime: {dt_str!r}")


def parse_ndk_records(path: str) -> list[dict]:
    """Parse one GCMT NDK file and return a list of event records.

    Each record dict contains the keys needed by :func:`match_events`:
    ``gcmt_id``, ``cen_time``, ``cen_lat``, ``cen_lon``, ``cen_depth``,
    ``scalar_moment`` (dyne-cm), ``strike``, ``dip``, ``rake``, ``mechanism``.

    Malformed 5-line groups are silently skipped.
    """
    with open(path) as f:
        raw = f.readlines()

    records: list[dict] = []
    i = 0
    while i + 4 < len(raw):
        line1 = raw[i].rstrip("\n")
        line2 = raw[i + 1].rstrip("\n")
        line3 = raw[i + 2].rstrip("\n")
        line4 = raw[i + 3].rstrip("\n")
        line5 = raw[i + 4].rstrip("\n")
        i += 5

        if not line1.strip():
            continue

        try:
            f1 = line1.split()
            f3 = line3.split()
            f4 = line4.split()
            f5 = line5.split()

            # Line 1: catalog date time lat lon depth ...
            ref_time = _parse_ndk_dt(f1[1], f1[2])

            # Line 2: gcmt_id is the first whitespace-delimited token
            gcmt_id = line2.split()[0]

            # Line 3: CENTROID: shift σ lat σ lon σ depth σ type timestamp
            time_shift = float(f3[1])
            cen_lat = float(f3[3])
            cen_lon = float(f3[5])
            cen_depth = float(f3[7])
            cen_time = ref_time + timedelta(seconds=time_shift)

            # Line 4: exponent Mrr σ Mtt σ Mpp σ Mrt σ Mrp σ Mtp σ
            exponent = int(f4[0])

            # Line 5: version T_val T_pl T_az N_val N_pl N_az P_val P_pl P_az
            #          scalar_moment NP1_s NP1_d NP1_r NP2_s NP2_d NP2_r
            scalar_moment = float(f5[10]) * (10 ** exponent)  # dyne-cm
            np1_strike = int(f5[11])
            np1_dip = int(f5[12])
            np1_rake = int(f5[13])

            records.append(
                {
                    "gcmt_id": gcmt_id,
                    "cen_time": cen_time,
                    "cen_lat": cen_lat,
                    "cen_lon": cen_lon,
                    "cen_depth": cen_depth,
                    "scalar_moment": scalar_moment,
                    "strike": np1_strike,
                    "dip": np1_dip,
                    "rake": np1_rake,
                    "mechanism": classify_mechanism(float(np1_rake)),
                }
            )
        except (IndexError, ValueError, KeyError):
            continue  # skip malformed 5-line groups

    return records


def load_gcmt_dir(gcmt_dir: str) -> list[dict]:
    """Load and merge all ``.ndk`` files from *gcmt_dir*, sorted by centroid time."""
    records: list[dict] = []
    for ndk_file in sorted(Path(gcmt_dir).glob("*.ndk")):
        records.extend(parse_ndk_records(str(ndk_file)))
    records.sort(key=lambda r: r["cen_time"])
    return records


# ---------------------------------------------------------------------------
# Event matching
# ---------------------------------------------------------------------------

def _gcmt_mw(scalar_moment_dyne_cm: float) -> float:
    """Compute Mw from scalar moment in dyne-cm."""
    if scalar_moment_dyne_cm <= 0:
        return 0.0
    return (2.0 / 3.0) * math.log10(scalar_moment_dyne_cm) - 10.7


def match_events(
    iscgem_events: list[dict],
    gcmt_records: list[dict],
    time_tol_s: float = 60.0,
    dist_km: float = 50.0,
    mag_tol: float = 0.3,
) -> list[dict]:
    """Join ISC-GEM events to GCMT records by spatial-temporal proximity.

    Algorithm:
    1. Sort GCMT records by centroid time.
    2. For each ISC-GEM event, binary-search the ±*time_tol_s* window.
    3. Among candidates, require distance ≤ *dist_km* and |ΔMw| ≤ *mag_tol*.
    4. Take the closest-in-time candidate as the match.

    Returns one dict per ISC-GEM event — all original columns plus the
    eight GCMT columns from :data:`APPEND_FIELDNAMES`.  Unmatched events
    receive empty strings for GCMT columns and ``match_confidence='null'``.
    """
    sorted_recs = sorted(gcmt_records, key=lambda r: r["cen_time"])
    cen_times = [r["cen_time"] for r in sorted_recs]

    _NULL = {
        "gcmt_id": "",
        "mechanism": "",
        "rake": "",
        "strike": "",
        "dip": "",
        "scalar_moment": "",
        "centroid_depth": "",
        "match_confidence": MATCH_NULL,
    }

    results: list[dict] = []
    for ev in iscgem_events:
        row = dict(ev)

        try:
            ev_time = datetime.fromisoformat(ev["event_at"].replace("Z", "+00:00"))
            ev_lat = float(ev["latitude"])
            ev_lon = float(ev["longitude"])
            ev_mag = float(ev["usgs_mag"])
        except (KeyError, ValueError):
            row.update(_NULL)
            results.append(row)
            continue

        tol = timedelta(seconds=time_tol_s)
        lo = bisect.bisect_left(cen_times, ev_time - tol)
        hi = bisect.bisect_right(cen_times, ev_time + tol)

        best: dict | None = None
        best_dt = float("inf")

        for rec in sorted_recs[lo:hi]:
            dt_s = abs((rec["cen_time"] - ev_time).total_seconds())
            d_km = haversine_km(ev_lat, ev_lon, rec["cen_lat"], rec["cen_lon"])
            dm = abs(_gcmt_mw(rec["scalar_moment"]) - ev_mag)

            if d_km <= dist_km and dm <= mag_tol and dt_s < best_dt:
                best_dt = dt_s
                best = rec

        if best is None:
            row.update(_NULL)
        else:
            row.update(
                {
                    "gcmt_id": best["gcmt_id"],
                    "mechanism": best["mechanism"],
                    "rake": best["rake"],
                    "strike": best["strike"],
                    "dip": best["dip"],
                    "scalar_moment": best["scalar_moment"],
                    "centroid_depth": best["cen_depth"],
                    "match_confidence": MATCH_PROXIMITY,
                }
            )

        results.append(row)

    return results
