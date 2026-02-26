# nornir-urd-two

## Purpose

Collect historical earthquake catalogs from the [USGS ISC-GEM / FDSN Event Web Service API](./review/usgs_data_source.md) and enrich each event with astronomical metrics that encode the gravitational geometry of the Sun and Moon at the time and location of the event. The enriched catalogs support statistical analysis of whether celestial body positioning and tidal forcing correlate with seismic activity.

**Note:** The project API request targets the **ISC-GEM** catalog *only*. This is to use the catalog which provides the most complete catalog for *historical* events. The ComCat catalog is best suited for users needing recent or real-time data, but does not provide historical completeness or magnitude adjustments. A more full project data source [discription is here](./review/usgs_data_source.md).

## Astronomical Metric Information

Each earthquake record is enriched with three custom astronomical metrics that describe the gravitational geometry of the Sun and Moon relative to the event. These metrics encode the positions of celestial bodies as simple integer values (elapsed seconds), making them suitable for statistical analysis of tidal stress influences on seismic activity.

- **[Solaration (`solar_secs`)](metric_info_solar.md)** --- Seconds elapsed since the preceding winter solstice. Tracks Earth's orbital position and maps directly to the Sun's declination angle, replacing the arbitrary civil calendar with an astronomically anchored annual cycle.

- **[Lunation (`lunar_secs`)](metric_info_lunar.md)** --- Seconds elapsed since the preceding new moon. Simultaneously encodes the Moon's orbital position and the Sun-Moon phase alignment, capturing the spring/neap tidal cycle that drives both ocean tides and the lesser-known earth tides (periodic crustal deformation).

- **[Midnight (`midnight_secs`)](metric_info_midnight.md)** --- Seconds elapsed since local solar midnight at the event's longitude. Uses a pure longitude-based time offset rather than civil time zones, providing an exact measure of the Sun's rotational position relative to the earthquake location.

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

# With custom parameters -- ~9,800 events
uv run python -m nornir_urd collect \
  --start 1949-12-25 --end 2021-12-20 \
  --min-mag 6.0 --max-mag 9.9 \
  --output data/output/global_events.csv
```

Output CSVs are saved to `data/output/`, which is gitignored to keep collected data out of version control.

### Query parameters

| Option            | Default        | Description                                |
| ----------------- | -------------- | ------------------------------------------ |
| `--output FILE`   | *(required)*   | Output CSV file path                       |
| `--start DATE`    | today - 5 days | Start date (ISO format, e.g. `2026-01-01`) |
| `--end DATE`      | today          | End date (ISO format)                      |
| `--min-mag FLOAT` | `6.0`          | Minimum magnitude                          |
| `--max-mag FLOAT` | `6.9`          | Maximum magnitude                          |
| `--min-lat FLOAT` |                | Minimum latitude                           |
| `--max-lat FLOAT` |                | Maximum latitude                           |
| `--min-lon FLOAT` |                | Minimum longitude                          |
| `--max-lon FLOAT` |                | Maximum longitude                          |

Example with a custom date range and geographic bounds:

```bash
uv run python -m nornir_urd collect \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --min-lat -10 --max-lat 10 \
  --output data/output/equatorial_2025.csv
```

### Output format

The output CSV contains the following columns:

`usgs_id, usgs_mag, event_at, solaration_year, solar_secs, lunar_secs, midnight_secs, latitude, longitude, depth`

### Decluster

Separate a catalog into mainshocks and aftershocks/foreshocks using the Gardner-Knopoff (1974) algorithm. This is a pure-Python implementation of the algorithm, even though other libraries exist and [were considered](review/no_open_quake.md):

```bash
uv run python -m nornir_urd decluster \
  --input data/output/global_events.csv \
  --mainshocks data/output/mainshocks.csv \
  --aftershocks data/output/aftershocks.csv
```

| Option               | Description                                            |
| -------------------- | ------------------------------------------------------ |
| `--input FILE`       | Input CSV file path                                    |
| `--mainshocks FILE`  | Output CSV for mainshock (independent) events          |
| `--aftershocks FILE` | Output CSV for aftershock/foreshock (dependent) events |

#### Declustering existing CSVs

The `decluster` command works on any CSV file, not just output from the `collect` command. The input CSV must contain these columns:

| Required column | Description                                      |
| --------------- | ------------------------------------------------ |
| `event_at`      | ISO 8601 timestamp (e.g. `2026-01-15T12:00:00Z`) |
| `latitude`      | Event latitude (float)                           |
| `longitude`     | Event longitude (float)                          |
| `usgs_mag`      | Event magnitude (float)                          |

All other columns present in the input are preserved in both output files.

#### Algorithm details and limitations

The implementation uses the Gardner-Knopoff (1974) empirical formulas for magnitude-dependent space-time windows:

- **Spatial window**: `d = 10^(0.1238 * M + 0.983)` km
- **Temporal window** (M < 6.5): `t = 10^(0.5409 * M - 0.547)` days
- **Temporal window** (M >= 6.5): `t = 10^(0.032 * M + 2.7389)` days

Distances are computed using the Haversine formula (spherical Earth, radius 6371 km). This introduces a minor approximation versus the WGS84 ellipsoid -- maximum error is ~0.3% (~0.5 km at the equator for a 150 km distance). At the spatial scales of the G-K windows (tens to hundreds of km), this is negligible relative to the uncertainty in the window parameters themselves.

The algorithm has O(n^2) time complexity (pairwise event comparison). This is efficient for catalogs up to ~50,000 events. For M6.0+ global catalogs (~100-200 events/year), runtime is effectively instant.

### Window

Run the Gardner-Knopoff algorithm with a scaled window and produce aftershock output enriched with parent attribution columns. `window` accepts the same input format as `decluster` but requires an explicit `--window-size` multiplier and adds four columns to the aftershock output:

```bash
uv run python -m nornir_urd window \
  --window-size 1.0 \
  --input data/output/global_events.csv \
  --mainshocks data/output/mainshocks.csv \
  --aftershocks data/output/aftershocks.csv
```

| Option               | Description                                                     |
| -------------------- | --------------------------------------------------------------- |
| `--window-size FLOAT` | *(required)* Scalar multiplier for both G-K window dimensions  |
| `--input FILE`       | Input CSV file path                                             |
| `--mainshocks FILE`  | Output CSV for mainshock (independent) events                   |
| `--aftershocks FILE` | Output CSV for aftershock/foreshock events (with extra columns) |

The `--window-size` multiplier is applied to both the spatial (km) and temporal (days) dimensions of the G-K windows. Values below `1.0` produce tighter windows (fewer events removed), values above `1.0` produce wider windows (more events removed).

#### Aftershock output columns

The aftershock CSV contains all columns from the input plus four attribution columns appended at the end:

| Column             | Description                                                                       |
| ------------------ | --------------------------------------------------------------------------------- |
| `parent_id`        | `usgs_id` of the mainshock whose window claimed this event                        |
| `parent_magnitude` | Magnitude of the parent mainshock                                                 |
| `delta_t_sec`      | Signed elapsed seconds from the parent to this event (negative for foreshocks)    |
| `delta_dist_km`    | Great-circle distance in km between this event and its parent                     |

When two mainshock windows overlap and both could claim the same event, the parent is the mainshock with the smallest `|delta_t_sec|` (temporal proximity takes priority over spatial proximity).

The mainshock output is identical in format to `decluster` — original columns only, no attribution metadata.

## Tests

```bash
uv run pytest tests/ -v
```
