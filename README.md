# nornir-urd-two

Verify and validate existing datasets. Generate new sample populations of historical data.

## Installation

Requires [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

### Ephemeris data

The astronomical calculations depend on the JPL DE421 ephemeris (`de421.bsp`, ~17 MB). Skyfield downloads this file automatically on first run into the working directory. It is excluded from version control via `.gitignore`.

To download it manually:

```bash
uv run python -c "from skyfield.api import load; load('de421.bsp')"
```

## Usage

Collect earthquake data from the USGS API and enrich it with astronomical calculations:

```bash
uv run python -m nornir_urd collect --output data/output/earthquakes.csv
```

Output CSVs are saved to `data/output/`, which is gitignored to keep collected data out of version control.

### Query parameters

| Option | Default | Description |
|---|---|---|
| `--output FILE` | *(required)* | Output CSV file path |
| `--start DATE` | today - 5 days | Start date (ISO format, e.g. `2026-01-01`) |
| `--end DATE` | today | End date (ISO format) |
| `--min-mag FLOAT` | `6.0` | Minimum magnitude |
| `--max-mag FLOAT` | `6.9` | Maximum magnitude |
| `--min-lat FLOAT` | | Minimum latitude |
| `--max-lat FLOAT` | | Maximum latitude |
| `--min-lon FLOAT` | | Minimum longitude |
| `--max-lon FLOAT` | | Maximum longitude |

Example with a custom date range and geographic bounds:

```bash
uv run python -m nornir_urd collect \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --min-lat -10 --max-lat 10 \
  --output data/output/equatorial_2025.csv
```

### Output format

The output CSV matches the legacy data format with the following columns:

`usgs_id, usgs_mag, event_at, solaration_year, solar_secs, lunar_secs, midnight_secs, longitude`

## Metric Information

Each earthquake record is enriched with three custom astronomical metrics that describe the gravitational geometry of the Sun and Moon relative to the event. These metrics encode the positions of celestial bodies as simple integer values (elapsed seconds), making them suitable for statistical analysis of tidal stress influences on seismic activity.

- **[Solaration (`solar_secs`)](metric_info_solar.md)** --- Seconds elapsed since the preceding winter solstice. Tracks Earth's orbital position and maps directly to the Sun's declination angle, replacing the arbitrary civil calendar with an astronomically anchored annual cycle.

- **[Lunation (`lunar_secs`)](metric_info_lunar.md)** --- Seconds elapsed since the preceding new moon. Simultaneously encodes the Moon's orbital position and the Sun-Moon phase alignment, capturing the spring/neap tidal cycle that drives both ocean tides and the lesser-known earth tides (periodic crustal deformation).

- **[Midnight (`midnight_secs`)](metric_info_midnight.md)** --- Seconds elapsed since local solar midnight at the event's longitude. Uses a pure longitude-based time offset rather than civil time zones, providing an exact measure of the Sun's rotational position relative to the earthquake location.

## Tests

```bash
uv run pytest tests/ -v
```
