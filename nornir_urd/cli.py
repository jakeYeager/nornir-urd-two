"""CLI for fetching and enriching earthquake data."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime, timedelta, timezone

from . import astro
from .decluster import (
    decluster_a1b_fixed,
    decluster_gardner_knopoff,
    decluster_gardner_knopoff_table,
    decluster_with_parents,
)
from .ocean import (
    OUTPUT_FIELDNAMES as OCEAN_FIELDNAMES,
    classify_events,
    load_coastline_vertices,
    load_pb2002_vertices,
)
from .pb2002 import parse_pb2002_steps, write_pb2002_types
from .reasenberg import decluster_reasenberg
from .usgs import fetch_earthquakes

OUTPUT_COLUMNS = [
    "usgs_id",
    "usgs_mag",
    "event_at",
    "solaration_year",
    "solar_secs",
    "lunar_secs",
    "midnight_secs",
    "latitude",
    "longitude",
    "depth",
]


def _parse_date(value: str) -> date:
    """Parse an ISO date string."""
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nornir-urd",
        description="Fetch USGS earthquake data and enrich with astronomical calculations.",
    )
    sub = parser.add_subparsers(dest="command")

    collect = sub.add_parser("collect", help="Collect earthquake data from USGS")
    collect.add_argument(
        "--start", type=_parse_date, default=None,
        help="Start date (ISO format, default: today - 5 days)",
    )
    collect.add_argument(
        "--end", type=_parse_date, default=None,
        help="End date (ISO format, default: today)",
    )
    collect.add_argument("--min-mag", type=float, default=6.0)
    collect.add_argument("--max-mag", type=float, default=6.9)
    collect.add_argument("--min-lat", type=float, default=None)
    collect.add_argument("--max-lat", type=float, default=None)
    collect.add_argument("--min-lon", type=float, default=None)
    collect.add_argument("--max-lon", type=float, default=None)
    collect.add_argument(
        "--catalog", type=str, default="iscgem",
        help="USGS catalog identifier (default: iscgem)",
    )
    collect.add_argument(
        "--output", required=True, help="Output CSV file path",
    )

    declust = sub.add_parser(
        "decluster",
        help="Decluster a CSV catalog using Gardner-Knopoff (1974)",
    )
    declust.add_argument(
        "--input", required=True,
        help="Input CSV file (must have event_at, latitude, longitude, usgs_mag columns)",
    )
    declust.add_argument(
        "--mainshocks", required=True,
        help="Output CSV path for mainshock events",
    )
    declust.add_argument(
        "--aftershocks", required=True,
        help="Output CSV path for aftershock/foreshock events",
    )

    # --- decluster-table ---------------------------------------------------
    dtable = sub.add_parser(
        "decluster-table",
        help=(
            "Decluster using the G-K (1974) discrete lookup table "
            "(not the continuous formula used by 'decluster')"
        ),
    )
    dtable.add_argument(
        "--input", required=True,
        help="Input CSV (must have event_at, latitude, longitude, usgs_mag)",
    )
    dtable.add_argument(
        "--mainshocks", required=True,
        help="Output CSV path for mainshock events",
    )
    dtable.add_argument(
        "--aftershocks", required=True,
        help="Output CSV path for aftershock/foreshock events",
    )

    # --- decluster-reasenberg ----------------------------------------------
    dreason = sub.add_parser(
        "decluster-reasenberg",
        help="Decluster using the Reasenberg (1985) interaction-based algorithm",
    )
    dreason.add_argument(
        "--input", required=True,
        help="Input CSV (must have event_at, latitude, longitude, usgs_mag)",
    )
    dreason.add_argument(
        "--mainshocks", required=True,
        help="Output CSV path for mainshock events",
    )
    dreason.add_argument(
        "--aftershocks", required=True,
        help="Output CSV path for aftershock/foreshock events",
    )
    dreason.add_argument(
        "--rfact", type=float, default=10.0,
        help="Interaction radius scale factor (default: 10)",
    )
    dreason.add_argument(
        "--tau-min", type=float, default=1.0,
        help="Minimum cluster lookback window in days (default: 1.0)",
    )
    dreason.add_argument(
        "--tau-max", type=float, default=10.0,
        help="Maximum cluster lookback window in days (default: 10.0)",
    )
    dreason.add_argument(
        "--p-value", type=float, default=0.95,
        help="Omori decay probability threshold for cluster termination (default: 0.95)",
    )
    dreason.add_argument(
        "--xmeff", type=float, default=1.5,
        help="Effective magnitude threshold (default: 1.5)",
    )

    # --- decluster-a1b -----------------------------------------------------
    da1b = sub.add_parser(
        "decluster-a1b",
        help="Decluster using fixed spatial and temporal windows (A1b-informed defaults)",
    )
    da1b.add_argument(
        "--input", required=True,
        help="Input CSV (must have event_at, latitude, longitude, usgs_mag)",
    )
    da1b.add_argument(
        "--mainshocks", required=True,
        help="Output CSV path for mainshock events",
    )
    da1b.add_argument(
        "--aftershocks", required=True,
        help="Output CSV path for aftershock/foreshock events",
    )
    da1b.add_argument(
        "--radius", type=float, default=83.2,
        help="Fixed spatial radius in km applied to all magnitudes (default: 83.2)",
    )
    da1b.add_argument(
        "--window", type=float, default=95.6,
        help="Fixed temporal window in days applied to all magnitudes (default: 95.6)",
    )

    # --- parse-pb2002 ------------------------------------------------------
    ppb = sub.add_parser(
        "parse-pb2002",
        help="Parse pb2002_steps.dat into a boundary-segment type lookup CSV",
    )
    ppb.add_argument(
        "--steps", default="lib/pb2002_steps.dat",
        help="Path to pb2002_steps.dat (default: lib/pb2002_steps.dat)",
    )
    ppb.add_argument(
        "--output", default="lib/pb2002_types.csv",
        help="Output CSV path (default: lib/pb2002_types.csv)",
    )

    # --- ocean-class -------------------------------------------------------
    oc = sub.add_parser(
        "ocean-class",
        help="Classify ISC-GEM events as oceanic, continental, or transitional",
    )
    oc.add_argument(
        "--input", required=True,
        help="Input CSV; must have usgs_id, latitude, longitude",
    )
    oc.add_argument(
        "--output", required=True,
        help="Output CSV (usgs_id, ocean_class, dist_to_coast_km)",
    )
    oc.add_argument(
        "--method", default="ne", choices=["ne", "gshhg", "pb2002"],
        help=(
            "Coastline data source: 'ne' (Natural Earth vertex CSV, default), "
            "'gshhg' (GSHHG vertex CSV), 'pb2002' (PB2002 boundary proxy)"
        ),
    )
    oc.add_argument(
        "--coastline", default="lib/ne_coastline_vertices.csv",
        help="Path to coastline vertex CSV for ne/gshhg methods "
             "(default: lib/ne_coastline_vertices.csv)",
    )
    oc.add_argument(
        "--pb2002-types", default="lib/pb2002_types.csv",
        help="Path to pb2002_types.csv for pb2002 method "
             "(default: lib/pb2002_types.csv)",
    )
    oc.add_argument(
        "--oceanic-km", type=float, default=200.0,
        help="Distance threshold (km): events beyond this are oceanic (default: 200)",
    )
    oc.add_argument(
        "--coastal-km", type=float, default=50.0,
        help="Distance threshold (km): events within this are continental (default: 50)",
    )

    # --- window ------------------------------------------------------------
    window_p = sub.add_parser(
        "window",
        help="Decluster with a scaled G-K window; aftershock output includes parent attribution",
    )
    window_p.add_argument(
        "--window-size", type=float, required=True,
        help="Scalar multiplier for G-K windows (e.g. 0.75 = tighter, 1.25 = wider)",
    )
    window_p.add_argument(
        "--input", required=True,
        help="Input CSV file (must have event_at, latitude, longitude, usgs_mag columns)",
    )
    window_p.add_argument(
        "--mainshocks", required=True,
        help="Output CSV path for mainshock events",
    )
    window_p.add_argument(
        "--aftershocks", required=True,
        help="Output CSV path for aftershock events (includes parent attribution columns)",
    )

    return parser


def _enrich(events: list[dict]) -> list[dict]:
    """Add astronomical fields to each event."""
    solstice_table = astro.build_solstice_table()
    new_moon_table = astro.build_new_moon_table()

    enriched = []
    for event in events:
        event_dt = datetime.fromisoformat(
            event["event_at"].replace("Z", "+00:00")
        )
        solaration_year, s_secs = astro.solar_secs(event_dt, solstice_table)
        l_secs = astro.lunar_secs(event_dt, new_moon_table)
        m_secs = astro.midnight_secs(event_dt, event["longitude"])

        enriched.append(
            {
                "usgs_id": event["usgs_id"],
                "usgs_mag": event["usgs_mag"],
                "event_at": event["event_at"],
                "solaration_year": solaration_year,
                "solar_secs": s_secs,
                "lunar_secs": l_secs,
                "midnight_secs": m_secs,
                "latitude": event["latitude"],
                "longitude": event["longitude"],
                "depth": event["depth"],
            }
        )
    return enriched


DECLUSTER_REQUIRED_COLUMNS = {"event_at", "latitude", "longitude", "usgs_mag"}

AFTERSHOCK_EXTRA_COLUMNS = ["parent_id", "parent_magnitude", "delta_t_sec", "delta_dist_km"]


def _run_collect(args: argparse.Namespace) -> None:
    today = date.today()
    start = args.start if args.start is not None else today - timedelta(days=5)
    end = args.end if args.end is not None else today

    events = fetch_earthquakes(
        start=start,
        end=end,
        min_mag=args.min_mag,
        max_mag=args.max_mag,
        min_lat=args.min_lat,
        max_lat=args.max_lat,
        min_lon=args.min_lon,
        max_lon=args.max_lon,
        catalog=args.catalog,
    )

    enriched = _enrich(events)

    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(enriched)

    print(f"Wrote {len(enriched)} events to {args.output}")


def _run_decluster(args: argparse.Namespace) -> None:
    fieldnames, events = _load_decluster_csv(args.input)
    mainshocks, aftershocks = decluster_gardner_knopoff(events)
    _write_mainshocks_aftershocks(args, fieldnames, mainshocks, aftershocks)


def _load_decluster_csv(path: str) -> tuple[list[str], list[dict]]:
    """Read a decluster-compatible CSV; cast numeric columns; return (fieldnames, events)."""
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        missing = DECLUSTER_REQUIRED_COLUMNS - set(fieldnames)
        if missing:
            print(f"Error: input CSV missing required columns: {', '.join(sorted(missing))}")
            sys.exit(1)
        events = list(reader)
    for event in events:
        event["latitude"] = float(event["latitude"])
        event["longitude"] = float(event["longitude"])
        event["usgs_mag"] = float(event["usgs_mag"])
    return fieldnames, events


def _write_mainshocks_aftershocks(
    args: argparse.Namespace,
    fieldnames: list[str],
    mainshocks: list[dict],
    aftershocks: list[dict],
) -> None:
    for path, rows, label in [
        (args.mainshocks, mainshocks, "mainshocks"),
        (args.aftershocks, aftershocks, "aftershocks"),
    ]:
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {len(rows)} {label} to {path}")


def _run_decluster_table(args: argparse.Namespace) -> None:
    fieldnames, events = _load_decluster_csv(args.input)
    mainshocks, aftershocks = decluster_gardner_knopoff_table(events)
    _write_mainshocks_aftershocks(args, fieldnames, mainshocks, aftershocks)


def _run_decluster_reasenberg(args: argparse.Namespace) -> None:
    fieldnames, events = _load_decluster_csv(args.input)
    mainshocks, aftershocks = decluster_reasenberg(
        events,
        rfact=args.rfact,
        tau_min=args.tau_min,
        tau_max=args.tau_max,
        p=args.p_value,
        xmeff=args.xmeff,
    )
    _write_mainshocks_aftershocks(args, fieldnames, mainshocks, aftershocks)


def _run_decluster_a1b(args: argparse.Namespace) -> None:
    fieldnames, events = _load_decluster_csv(args.input)
    mainshocks, aftershocks = decluster_a1b_fixed(
        events,
        radius_km=args.radius,
        window_days=args.window,
    )
    _write_mainshocks_aftershocks(args, fieldnames, mainshocks, aftershocks)


def _run_parse_pb2002(args: argparse.Namespace) -> None:
    rows = parse_pb2002_steps(args.steps)
    write_pb2002_types(rows, args.output)
    print(f"Wrote {len(rows)} boundary segments to {args.output}")


def _run_ocean_class(args: argparse.Namespace) -> None:
    with open(args.input, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        missing = {"usgs_id", "latitude", "longitude"} - set(fieldnames)
        if missing:
            print(f"Error: input CSV missing required columns: {', '.join(sorted(missing))}")
            sys.exit(1)
        events = list(reader)

    if args.method == "pb2002":
        vertices = load_pb2002_vertices(args.pb2002_types)
    else:
        vertices = load_coastline_vertices(args.coastline)

    results = classify_events(
        events,
        vertices,
        oceanic_km=args.oceanic_km,
        coastal_km=args.coastal_km,
    )

    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OCEAN_FIELDNAMES)
        writer.writeheader()
        writer.writerows(results)
    print(f"Wrote {len(results)} classified events to {args.output}")


def _run_window(args: argparse.Namespace) -> None:
    with open(args.input, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        missing = DECLUSTER_REQUIRED_COLUMNS - set(fieldnames)
        if missing:
            print(f"Error: input CSV missing required columns: {', '.join(sorted(missing))}")
            sys.exit(1)
        events = list(reader)

    for event in events:
        event["latitude"] = float(event["latitude"])
        event["longitude"] = float(event["longitude"])
        event["usgs_mag"] = float(event["usgs_mag"])

    mainshocks, aftershocks = decluster_with_parents(events, window_scale=args.window_size)

    aftershock_fieldnames = fieldnames + AFTERSHOCK_EXTRA_COLUMNS

    with open(args.mainshocks, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(mainshocks)
    print(f"Wrote {len(mainshocks)} mainshocks to {args.mainshocks}")

    with open(args.aftershocks, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=aftershock_fieldnames)
        writer.writeheader()
        writer.writerows(aftershocks)
    print(f"Wrote {len(aftershocks)} aftershocks to {args.aftershocks}")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "collect":
        _run_collect(args)
    elif args.command == "decluster":
        _run_decluster(args)
    elif args.command == "decluster-table":
        _run_decluster_table(args)
    elif args.command == "decluster-reasenberg":
        _run_decluster_reasenberg(args)
    elif args.command == "decluster-a1b":
        _run_decluster_a1b(args)
    elif args.command == "parse-pb2002":
        _run_parse_pb2002(args)
    elif args.command == "ocean-class":
        _run_ocean_class(args)
    elif args.command == "window":
        _run_window(args)
    else:
        parser.print_help()
        sys.exit(1)
