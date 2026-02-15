"""CLI for fetching and enriching earthquake data."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime, timedelta, timezone

from . import astro
from .usgs import fetch_earthquakes

OUTPUT_COLUMNS = [
    "usgs_id",
    "usgs_mag",
    "event_at",
    "solaration_year",
    "solar_secs",
    "lunar_secs",
    "midnight_secs",
    "longitude",
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
                "longitude": event["longitude"],
            }
        )
    return enriched


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "collect":
        parser.print_help()
        sys.exit(1)

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
