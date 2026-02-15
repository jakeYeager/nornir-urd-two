"""Validate legacy earthquake data against Skyfield-based calculations.

Loads data/legacy_data.csv, recomputes solar_secs, lunar_secs, and
midnight_secs using nornir_urd.astro, then writes a comparison CSV
and a summary report.
"""

from __future__ import annotations

import csv
import statistics
from datetime import datetime, timezone
from pathlib import Path

from nornir_urd.astro import (
    build_new_moon_table,
    build_solstice_table,
    lunar_secs,
    midnight_secs,
    solar_secs,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEGACY_CSV = PROJECT_ROOT / "data" / "legacy_data.csv"
COMPARISON_CSV = PROJECT_ROOT / "validation" / "legacy_comparison.csv"
REPORT_MD = PROJECT_ROOT / "review" / "legacy_data_report.md"


def load_legacy_rows() -> list[dict]:
    with open(LEGACY_CSV, newline="") as f:
        return list(csv.DictReader(f))


def parse_event_at(raw: str) -> datetime:
    return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def run_validation() -> list[dict]:
    """Recompute all fields and return comparison rows."""
    print("Building solstice table...")
    solstice_table = build_solstice_table(1948, 2051)
    print("Building new moon table...")
    new_moon_table = build_new_moon_table(1948, 2051)

    rows = load_legacy_rows()
    print(f"Loaded {len(rows)} legacy records.")

    results = []
    for row in rows:
        event_at = parse_event_at(row["event_at"])
        lon = float(row["longitude"])

        legacy_solar = int(float(row["solar_secs"]))
        legacy_lunar = int(float(row["lunar_secs"]))
        legacy_midnight = int(float(row["midnight_secs"]))

        legacy_solaration_year = int(float(row["solaration_year"]))
        new_solaration_year, new_solar = solar_secs(event_at, solstice_table)
        new_lunar = lunar_secs(event_at, new_moon_table)
        new_midnight = midnight_secs(event_at, lon)

        results.append({
            "usgs_id": row["usgs_id"],
            "event_at": row["event_at"],
            "legacy_solaration_year": legacy_solaration_year,
            "new_solaration_year": new_solaration_year,
            "legacy_solar_secs": legacy_solar,
            "new_solar_secs": new_solar,
            "solar_delta": new_solar - legacy_solar,
            "legacy_lunar_secs": legacy_lunar,
            "new_lunar_secs": new_lunar,
            "lunar_delta": new_lunar - legacy_lunar,
            "legacy_midnight_secs": legacy_midnight,
            "new_midnight_secs": new_midnight,
            "midnight_delta": new_midnight - legacy_midnight,
        })

    return results


def write_comparison_csv(results: list[dict]) -> None:
    fieldnames = [
        "usgs_id", "event_at",
        "legacy_solaration_year", "new_solaration_year",
        "legacy_solar_secs", "new_solar_secs", "solar_delta",
        "legacy_lunar_secs", "new_lunar_secs", "lunar_delta",
        "legacy_midnight_secs", "new_midnight_secs", "midnight_delta",
    ]
    with open(COMPARISON_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"Wrote comparison CSV: {COMPARISON_CSV}")


def field_stats(results: list[dict], key: str) -> dict:
    values = [r[key] for r in results]
    abs_values = [abs(v) for v in values]
    return {
        "min": min(values),
        "max": max(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "abs_mean": statistics.mean(abs_values),
        "abs_median": statistics.median(abs_values),
    }


def write_report(results: list[dict]) -> None:
    solar_stats = field_stats(results, "solar_delta")
    lunar_stats = field_stats(results, "lunar_delta")
    midnight_stats = field_stats(results, "midnight_delta")

    lunar_gt_60 = [r for r in results if abs(r["lunar_delta"]) > 60]
    midnight_nonzero = [r for r in results if r["midnight_delta"] != 0]

    lines = [
        "# Legacy Data Validation Report",
        "",
        f"**Records validated:** {len(results)}",
        "",
        "## Solar Secs Delta",
        "",
        "Legacy used `YYYY/12/21T00:00:00Z` as the solstice reference;",
        "our ephemeris uses the actual astronomical solstice time.",
        "",
        f"- Min: {solar_stats['min']:,}s ({solar_stats['min'] / 86400:.2f} days)",
        f"- Max: {solar_stats['max']:,}s ({solar_stats['max'] / 86400:.2f} days)",
        f"- Mean: {solar_stats['mean']:,.1f}s ({solar_stats['mean'] / 86400:.2f} days)",
        f"- Median: {solar_stats['median']:,.1f}s ({solar_stats['median'] / 86400:.2f} days)",
        f"- Abs Mean: {solar_stats['abs_mean']:,.1f}s ({solar_stats['abs_mean'] / 86400:.2f} days)",
        f"- Abs Median: {solar_stats['abs_median']:,.1f}s ({solar_stats['abs_median'] / 86400:.2f} days)",
        "",
        "## Lunar Secs Delta",
        "",
        f"- Min: {lunar_stats['min']}s",
        f"- Max: {lunar_stats['max']}s",
        f"- Mean: {lunar_stats['mean']:.1f}s",
        f"- Median: {lunar_stats['median']:.1f}s",
        f"- Records with |delta| > 60s: **{len(lunar_gt_60)}**",
        "",
    ]

    if lunar_gt_60:
        lines.append("### Lunar anomalies (|delta| > 60s)")
        lines.append("")
        lines.append("| usgs_id | event_at | legacy | new | delta |")
        lines.append("|---------|----------|-------:|----:|------:|")
        for r in lunar_gt_60[:50]:  # cap display at 50
            lines.append(
                f"| {r['usgs_id']} | {r['event_at']} "
                f"| {r['legacy_lunar_secs']} | {r['new_lunar_secs']} "
                f"| {r['lunar_delta']} |"
            )
        if len(lunar_gt_60) > 50:
            lines.append(f"| ... | ({len(lunar_gt_60) - 50} more) | | | |")
        lines.append("")

    lines.extend([
        "## Midnight Secs Delta",
        "",
        f"- Min: {midnight_stats['min']}s",
        f"- Max: {midnight_stats['max']}s",
        f"- Mean: {midnight_stats['mean']:.1f}s",
        f"- Median: {midnight_stats['median']:.1f}s",
        f"- Records with delta != 0: **{len(midnight_nonzero)}**",
        "",
    ])

    if midnight_nonzero:
        lines.append("### Midnight anomalies (delta != 0)")
        lines.append("")
        lines.append("| usgs_id | event_at | longitude | legacy | new | delta |")
        lines.append("|---------|----------|----------:|-------:|----:|------:|")
        for r in midnight_nonzero[:20]:
            lines.append(
                f"| {r['usgs_id']} | {r['event_at']} "
                f"| - | {r['legacy_midnight_secs']} | {r['new_midnight_secs']} "
                f"| {r['midnight_delta']} |"
            )
        if len(midnight_nonzero) > 20:
            lines.append(f"| ... | ({len(midnight_nonzero) - 20} more) | | | | |")
        lines.append("")

    report = "\n".join(lines) + "\n"
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report)
    print(f"Wrote report: {REPORT_MD}")


def main():
    results = run_validation()
    write_comparison_csv(results)
    write_report(results)
    print("Validation complete.")


if __name__ == "__main__":
    main()
