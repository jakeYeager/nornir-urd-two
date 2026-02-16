"""CLI for fetching and enriching earthquake data."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime, timedelta, timezone

from . import astro
from .decluster import decluster_gardner_knopoff
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
    )

    enriched = _enrich(events)

    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(enriched)

    print(f"Wrote {len(enriched)} events to {args.output}")


def _run_decluster(args: argparse.Namespace) -> None:
    with open(args.input, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        missing = DECLUSTER_REQUIRED_COLUMNS - set(fieldnames)
        if missing:
            print(f"Error: input CSV missing required columns: {', '.join(sorted(missing))}")
            sys.exit(1)
        events = list(reader)

    # csv.DictReader returns strings; cast numeric fields
    for event in events:
        event["latitude"] = float(event["latitude"])
        event["longitude"] = float(event["longitude"])
        event["usgs_mag"] = float(event["usgs_mag"])

    mainshocks, aftershocks = decluster_gardner_knopoff(events)

    for path, rows, label in [
        (args.mainshocks, mainshocks, "mainshocks"),
        (args.aftershocks, aftershocks, "aftershocks"),
    ]:
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {len(rows)} {label} to {path}")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "collect":
        _run_collect(args)
    elif args.command == "decluster":
        _run_decluster(args)
    else:
        parser.print_help()
        sys.exit(1)
