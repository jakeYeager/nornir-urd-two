# Phased Implementation Plan: Topic A2 Data Requirements

**Date:** 2026-02-27
**Source:** `review/06_data_analysis_reqs.md`, `claude/plans/06_feasibility.md`
**Output location:** `.claude/plans/06_phases.md`

---

## Design Decisions Applied

- All data output paths use `data/output/` as canonical (not `data/global-sets/` or `data/declustering/`).
- G-K formula-based `decluster` subcommand is unchanged. A new table-based `decluster-table` subcommand is added alongside it.
- G-K table values must be verified against the original Gardner & Knopoff (1974) paper before `decluster-table` is implemented.
- REQ-2 coastline classification defaults to Option B (pure stdlib, pre-computed vertex CSV). All three methods exposed via `--method` flag.
- GCMT files (REQ-4) follow offline-first pattern: user populates `lib/gcmt/` manually.
- Each phase is self-contained: no phase requires another phase's code to exist first.

---

## Phase Sequence

| Phase | Serves Cases | REQ(s) | Priority | Status |
|---|---|---|---|---|
| 1 | A4, A1 | REQ-1 | Critical | **Complete** (commit 6159572) |
| 2 | B2 | REQ-2, REQ-5 | Medium | **Complete** |
| 3 | B3 | REQ-4, REQ-5 (data only) | Medium | **Complete** |
| 4 | B5 | REQ-3 | Low | **Complete** |

**Cases with no pipeline work** (derivable at analysis time): B6 (raw catalog already at `data/output/iscgem_global_events.csv`), B1, A3, B4, A2.

---

## Phase 1 — ISC-GEM Declustered Catalogs

**Serves:** A4 (execute first), A1 (uses A4 outputs)
**REQ:** REQ-1
**Priority:** Critical

### Pre-implementation task
Verify the G-K table values in REQ-1 against the original Gardner & Knopoff (1974) paper before writing `gk_window_table()`. The feasibility study identified a significant divergence between the current formula's temporal values (e.g., ~499 days at M=6.0) and the REQ-1 table (915 days at M=6.0). Confirm which is authoritative before coding.

### New subcommand: `decluster-table`

G-K declustering using the discrete lookup table from the 1974 paper directly (not the continuous formula used by `decluster`).

```
nornir-urd decluster-table --input <path> --mainshocks <path> --aftershocks <path>
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--input` | yes | — | Input CSV; must have `event_at`, `latitude`, `longitude`, `usgs_mag` |
| `--mainshocks` | yes | — | Output CSV for retained mainshock events |
| `--aftershocks` | yes | — | Output CSV for removed aftershock/foreshock events |

Schema: same as input (all columns preserved). Mainshock/aftershock split conveyed by file membership only — no additional columns added.

**Note:** This subcommand uses the discrete G-K (1974) table, NOT the continuous empirical formula. See `nornir_urd/decluster.py:gk_window_table()` for table values and source reference.

### New subcommand: `decluster-reasenberg`

Reasenberg (1985) cluster analysis using published default parameters.

```
nornir-urd decluster-reasenberg --input <path> --mainshocks <path> --aftershocks <path> [options]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--input` | yes | — | Input CSV; must have `event_at`, `latitude`, `longitude`, `usgs_mag` |
| `--mainshocks` | yes | — | Output CSV for mainshock events |
| `--aftershocks` | yes | — | Output CSV for aftershock/foreshock events |
| `--rfact` | no | `10` | Interaction radius factor (multiples of location uncertainty) |
| `--tau-min` | no | `1.0` | Minimum cluster lookback window (days) |
| `--tau-max` | no | `10.0` | Maximum cluster lookback window (days) |
| `--p-value` | no | `0.95` | Omori decay probability threshold for cluster termination |
| `--xmeff` | no | `1.5` | Effective magnitude threshold |

Schema: same as `decluster-table`. Published defaults match Reasenberg (1985); override only for sensitivity analysis.

### New subcommand: `decluster-a1b`

Fixed spatial-temporal window declustering using the A1b-informed parameters (83.2 km radius, 95.6-day window for all magnitudes).

```
nornir-urd decluster-a1b --input <path> --mainshocks <path> --aftershocks <path> [options]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--input` | yes | — | Input CSV; must have `event_at`, `latitude`, `longitude`, `usgs_mag` |
| `--mainshocks` | yes | — | Output CSV for mainshock events |
| `--aftershocks` | yes | — | Output CSV for aftershock/foreshock events |
| `--radius` | no | `83.2` | Fixed spatial radius (km) applied to all magnitudes |
| `--window` | no | `95.6` | Fixed temporal window (days) applied to all magnitudes |

Schema: same as `decluster-table`. Defaults are the A1b-derived values; `--radius` and `--window` are exposed for sensitivity analysis only.

### Files changed

| Action | Path |
|---|---|
| Add `gk_window_table()`, `decluster_gardner_knopoff_table()`, `decluster_a1b_fixed()` | `nornir_urd/decluster.py` |
| New module: Reasenberg (1985) algorithm | `nornir_urd/reasenberg.py` |
| Add subparsers + handlers for three new subcommands | `nornir_urd/cli.py` |
| New test class for table-based G-K window values | `tests/test_decluster.py` |
| New test module for Reasenberg | `tests/test_reasenberg.py` |
| Update ephemeris section | `README.md` |

### Expected output files

```
data/output/iscgem_gk_table_mainshocks.csv
data/output/iscgem_gk_table_aftershocks.csv
data/output/iscgem_reasenberg_mainshocks.csv
data/output/iscgem_reasenberg_aftershocks.csv
data/output/iscgem_a1b_mainshocks.csv
data/output/iscgem_a1b_aftershocks.csv
```

---

## Phase 2 — Ocean/Continent Classification + PB2002 Type Parsing

**Serves:** B2
**REQ:** REQ-2 (primary), REQ-5 (supplement)
**Priority:** Medium

### User-supplied data (acquire before running)

1. **Coastline vertex CSV** — Convert Natural Earth `ne_10m_coastline` shapefile to a two-column `lon,lat` CSV and place at `lib/ne_coastline_vertices.csv`. Conversion instructions in README. (~3–4 MB)
2. **`lib/pb2002_steps.dat`** — Download from [peterbird.name/publications/2003_PB2002](https://peterbird.name/publications/2003_PB2002/2003_PB2002.htm). Required to run `parse-pb2002`. (~50 KB)

### New subcommand: `parse-pb2002`

Parses `pb2002_steps.dat` into a structured CSV lookup (`lib/pb2002_types.csv`) usable by `ocean-class --method pb2002` and Phase 3 (B3 fallback tectonic regime).

```
nornir-urd parse-pb2002 [--steps <path>] [--output <path>]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--steps` | no | `lib/pb2002_steps.dat` | Path to PB2002 steps file |
| `--output` | no | `lib/pb2002_types.csv` | Output CSV path |

Output schema: `segment_id, plate_a, plate_b, boundary_type_code, boundary_type_label, lon, lat`

Boundary type codes: CTF, CRB, CCB, OSR, OTF, OCB, SUB (Bird 2003).

### New subcommand: `ocean-class`

Classifies each event as `oceanic`, `continental`, or `transitional` based on distance to nearest coastline.

```
nornir-urd ocean-class --input <path> --output <path> [options]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--input` | yes | — | Input CSV; must have `usgs_id`, `latitude`, `longitude` |
| `--output` | yes | — | Output CSV: `usgs_id, ocean_class, dist_to_coast_km` |
| `--method` | no | `ne` | Coastline source: `ne` (Natural Earth vertex CSV), `gshhg` (GSHHG vertex CSV), `pb2002` (PB2002 boundary proxy) |
| `--coastline` | no | `lib/ne_coastline_vertices.csv` | Path to coastline vertex CSV (used for `ne` and `gshhg` methods) |
| `--pb2002-types` | no | `lib/pb2002_types.csv` | Path to PB2002 types CSV (used for `pb2002` method) |
| `--oceanic-km` | no | `200` | Events > this distance from coast are `oceanic` |
| `--coastal-km` | no | `50` | Events ≤ this distance from coast are `continental`; between is `transitional` |

**Method notes:**
- `ne` (default): Option B — pure stdlib Haversine scan against pre-computed Natural Earth vertex CSV. No extra dependencies. Recommended.
- `gshhg`: Same algorithm; GSHHG vertex CSV as input. Higher resolution. No extra dependencies.
- `pb2002`: Option C — uses PB2002 plate boundary segments as a coarse coastline proxy. Lower accuracy but requires no external coastline data beyond `lib/pb2002_types.csv`. Not recommended for primary analysis.

For Option A (`shapely` + shapefile) as a higher-accuracy alternative: not implemented in this phase due to medium-low priority, but noted in code comments as a future upgrade path.

### Files changed

| Action | Path |
|---|---|
| New module: PB2002 steps parser | `nornir_urd/pb2002.py` |
| New module: ocean classification (Haversine scan + thresholding) | `nornir_urd/ocean.py` |
| Add subparsers + handlers for `parse-pb2002` and `ocean-class` | `nornir_urd/cli.py` |
| New tests | `tests/test_pb2002.py`, `tests/test_ocean.py` |
| Add data setup instructions | `README.md` |

### Expected output files

```
lib/pb2002_types.csv              (reference file, produced by parse-pb2002)
data/output/iscgem_ocean_class.csv
```

---

## Phase 3 — GCMT Focal Mechanism Join

**Serves:** B3
**REQ:** REQ-4 (primary), REQ-5 data (`lib/pb2002_types.csv`, produced in Phase 2)
**Priority:** Medium

### User-supplied data (acquire before running)

Download GCMT NDK files covering M ≥ 6.0, 1976–2021 from [globalcmt.org/CMTfiles.html](https://www.globalcmt.org/CMTfiles.html) and place all `.ndk` files in `lib/gcmt/`. The subcommand scans the directory for all `.ndk` files automatically. Total size: ~50 MB. Pre-1976 ISC-GEM events receive `mechanism = null` (GCMT catalog starts 1976).

### New subcommand: `focal-join`

Parses GCMT NDK files, matches events to ISC-GEM catalog using spatial-temporal proximity, classifies focal mechanism type from rake angle, and outputs a join table.

```
nornir-urd focal-join --input <path> --output <path> [options]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--input` | yes | — | Input CSV; must have `usgs_id`, `event_at`, `latitude`, `longitude`, `usgs_mag` |
| `--output` | yes | — | Output CSV (all input columns retained; new columns appended — schema below) |
| `--gcmt-dir` | no | `lib/gcmt/` | Directory containing GCMT `.ndk` files |
| `--time-tol` | no | `60` | Match tolerance: seconds |
| `--dist-km` | no | `50` | Match tolerance: kilometers |
| `--mag-tol` | no | `0.3` | Match tolerance: magnitude units |

Output schema: all columns from input CSV, plus `gcmt_id, mechanism, rake, strike, dip, scalar_moment, centroid_depth, match_confidence`

`match_confidence` values: `exact_id` (GCMT ID cross-references ISC-GEM ID), `proximity` (matched by time/location/magnitude), `null` (no match).

Mechanism classification from rake angle:
- `thrust`: rake ∈ [45°, 135°]
- `normal`: rake ∈ [−135°, −45°]
- `strike_slip`: rake ∈ (−45°, 45°] ∪ (135°, 180°] ∪ [−180°, −135°)
- `oblique`: dominant component classification where rake falls near boundaries

### Files changed

| Action | Path |
|---|---|
| New module: NDK parser, event matcher, mechanism classifier | `nornir_urd/gcmt.py` |
| Add subparser + handler for `focal-join` | `nornir_urd/cli.py` |
| New tests (NDK parsing, mechanism classification, matching logic) | `tests/test_gcmt.py` |
| Add GCMT data setup instructions | `README.md` |

### Expected output files

```
data/output/iscgem_focal_mechanisms.csv
```

---

## Phase 4 — Solar Geometry Columns

**Serves:** B5
**REQ:** REQ-3
**Priority:** Low

No user-supplied data required. `lib/de421.bsp` already present.

### New subcommand: `solar-geometry`

Computes three ephemeris-derived columns per event using the existing Skyfield + DE421 setup.

```
nornir-urd solar-geometry --input <path> --output <path>
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--input` | yes | — | Input CSV; must have `usgs_id`, `event_at` |
| `--output` | yes | — | Output CSV (all input columns retained; new columns appended — schema below) |

Output schema: all columns from input CSV, plus the three new ephemeris columns:

| New column | Units | Range | Method |
|---|---|---|---|
| `solar_declination` | degrees | −23.5 to +23.5 | Sun apparent declination via Skyfield radec() |
| `declination_rate` | degrees/day | ~−0.40 to +0.40 | Finite difference of `solar_declination` at t ± 0.5 days |
| `earth_sun_distance` | AU | ~0.983 to ~1.017 | Earth-Sun distance from DE421 ephemeris |

### Files changed

| Action | Path |
|---|---|
| Add `solar_geometry()` function | `nornir_urd/astro.py` |
| Add subparser + handler for `solar-geometry` | `nornir_urd/cli.py` |
| Extend existing astro tests | `tests/test_astro.py` |

### Expected output files

```
data/output/iscgem_solar_geometry.csv
```

---

## Full Subcommand Inventory (post all phases)

| Subcommand | Phase | Status |
|---|---|---|
| `collect` | — | Existing |
| `decluster` | — | Existing (G-K formula-based) |
| `window` | — | Existing (G-K formula-based, scaled, with parent attribution) |
| `decluster-table` | 1 | New — G-K 1974 lookup table |
| `decluster-reasenberg` | 1 | New — Reasenberg (1985) |
| `decluster-a1b` | 1 | New — A1b fixed-window |
| `parse-pb2002` | 2 | New — PB2002 steps → types CSV |
| `ocean-class` | 2 | New — ocean/continent/transitional classification |
| `focal-join` | 3 | New — GCMT focal mechanism join |
| `solar-geometry` | 4 | New — solar declination + Earth-Sun distance |
