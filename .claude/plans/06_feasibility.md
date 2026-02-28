# Feasibility Study: Topic A2 Data Requirements

**Date:** 2026-02-27
**Source:** `review/06_data_analysis_reqs.md`
**Output location:** `.claude/plans/06_feasibility.md`

---

## Summary Verdict

All five requirements are feasible within this project. REQ-3 requires no new dependencies. REQ-1 (G-K and A1b variants) and REQ-5 require minimal new code. REQ-1 (Reasenberg) requires a pure-Python implementation from paper spec. REQ-2 requires one new dependency (`shapely`) and a coastline data file. REQ-4 is the most complex but remains tractable with existing tooling (`httpx` already present).

---

## REQ-1: ISC-GEM Declustered Catalogs (3 variants)

### Source data
The ISC-GEM catalog is at `data/output/iscgem_global_events.csv` (9,210 events). The requirement references `data/global-sets/iscgem_global_events.csv` — this path does not yet exist. The output directories `data/declustering/` and `data/global-sets/` also do not yet exist and will need to be created.

### G-K variant
**Status: Largely implemented; one concern.**

`decluster_gardner_knopoff()` and `gk_window()` are implemented in `decluster.py`. The current implementation uses the continuous empirical formula. REQ-1 specifies using "the above values from the 1974 paper directly" (the discrete lookup table). Comparing the formula output against the REQ-1 table reveals a discrepancy in the temporal window for M < 6.5:

| M | Formula T (days) | Table T (days) |
|---|---|---|
| 5.0 | ~144 | 510 |
| 5.5 | ~263 | 790 |
| 6.0 | ~499 | 915 |
| 6.5 | ~885 (M>=6.5 formula) | 960 |
| 7.0 | ~918 | 985 |

Spatial windows are consistent (within ~1 km). The time formula for M < 6.5 diverges significantly from the table values. **This needs to be resolved before implementation: should the G-K variant use the continuous formula (current behavior) or the discrete lookup table?**

The `decluster` subcommand already runs G-K on any input CSV. The only work required is pointing it at the ISC-GEM catalog and writing to `data/declustering/`.

### Reasenberg (1985) variant
**Status: Requires pure-Python implementation.**

No Python package provides a ready-to-use Reasenberg implementation without heavy dependencies (ZMAP is MATLAB; seismological Python packages with Reasenberg such as `obspy` or `pycsep` carry substantial dependency weight — contrary to this project's design philosophy).

The algorithm is fully specified in the REQ-1 description: `r_fact=10`, `tau_min=1 day`, `tau_max=10 days`, `p=0.95`, `xmeff=1.5`. This is implementable in pure Python using only stdlib (`math`, `datetime`). The core logic involves:

1. Sorting events chronologically.
2. For each event, checking if it falls within an active cluster's interaction zone (magnitude-dependent radius, growing with time).
3. Cluster interaction time τ adapts based on Omori aftershock decay using p-value.

Estimated complexity: ~150–200 lines of pure Python. No new dependencies required. The Haversine function from `decluster.py` is reusable.

### A1b-informed custom window variant
**Status: Trivial — minor extension of existing code.**

Fixed spatial radius 83.2 km and fixed temporal window 95.6 days for all magnitudes. This is a degenerate case of the existing G-K algorithm where `gk_window()` always returns `(83.2, 95.6)`. Can be implemented as a thin wrapper around the existing `decluster_gardner_knopoff()` with a custom window function passed in, or as a standalone function. No new dependencies required.

---

## REQ-2: Ocean/Continent Classification Column

**Status: Feasible; requires one new dependency and a data file.**

The preferred approach is Natural Earth coastline data with Haversine distance computation. Three implementation options:

**Option A — `shapely` + Natural Earth (preferred per REQ-2):**
`shapely` is not currently installed. It is pure-Python-compatible and lightweight (no compiled binary required on modern systems via wheel). The Natural Earth `ne_10m_coastline` shapefile (~1.7 MB) would need to be sourced and stored in `lib/`. Coastline vertices can be read without `geopandas` using only `shapely`.

**Option B — Pure stdlib with stored coastline vertices:**
The Natural Earth coastline can be pre-converted to a CSV of `(lon, lat)` vertex coordinates and stored in `lib/`. Distance to nearest vertex computed with `haversine_km()` (already in `decluster.py`). Zero new Python dependencies; larger data file (~3–4 MB CSV). Slower but self-contained.

**Option C — PB2002 as fallback (already present):**
`lib/pb2002_boundaries.dig` exists and is parsed. Plate boundaries don't follow coastlines exactly — as noted in REQ-2, this is not recommended except as a last resort.

**Recommendation for feasibility:** Option A with `shapely` is the cleanest. Option B is viable if keeping zero new runtime dependencies is a priority. Both are feasible. **Which approach is preferred?**

Output: `data/global-sets/iscgem_ocean_class.csv` (`usgs_id`, `ocean_class`, `dist_to_coast_km`).

---

## REQ-3: Solar Declination and Earth-Sun Distance Columns

**Status: Fully feasible. No new dependencies.**

Skyfield 1.54 and DE421 are already present and loaded in `astro.py`. All three columns are computable at event time using the existing ephemeris:

- `solar_declination`: Sun's apparent declination via `earth.at(t).observe(sun).apparent().radec()` — the declination is the second element in degrees.
- `declination_rate`: Finite difference of `solar_declination` at t±0.5 days. Two additional Skyfield time computations per event.
- `earth_sun_distance`: `earth.at(t).observe(sun).apparent().distance().au`.

Implementation: a new function in `astro.py` (~25 lines), similar in structure to the existing `solar_secs()`. Output goes to `data/global-sets/iscgem_solar_geometry.csv`.

---

## REQ-4: GCMT Focal Mechanism Catalog

**Status: Feasible; most complex of the five requirements.**

**Data acquisition:** GCMT provides period-based NDK files at `globalcmt.org`. `httpx` (already a dependency) can fetch these. NDK is a fixed-width text format — no external parser needed. Approximate download: ~50 MB total for M≥6.0, 1976–2021.

**NDK parsing:** Each event record is 5 lines with fixed column positions. Pure Python implementation; no new dependencies. Fields needed: origin time, latitude, longitude, magnitude, moment tensor components (for rake derivation), scalar moment.

**Rake/mechanism classification:** Rake is derived from the nodal plane in the moment tensor. Formula is standard (`atan2` of moment tensor components). Pure Python, no dependencies.

**Event matching (ISC-GEM ↔ GCMT):** Spatial-temporal proximity join — ±60s, 50 km, ±0.3 magnitude. O(n×m) scan over 9,210 ISC-GEM events × ~20,000 GCMT events. At this scale (~180M comparisons) a pure-Python nested loop will be slow (~minutes). A time-sorted approach with a window lookup can reduce this to O(n log m) and run in seconds. Feasible without numpy.

**Coverage gap:** GCMT begins in 1976. Pre-1976 ISC-GEM events (~15% of catalog) will have `mechanism = null`.

**Output:** `data/global-sets/iscgem_focal_mechanisms.csv` with schema as specified.

---

## REQ-5: PB2002 Boundary Type Classification

**Status: Feasible; straightforward data acquisition and parsing.**

`lib/pb2002_boundaries.dig` is already present. The required `pb2002_steps.dat` file is available from the same source (peterbird.name). It is a fixed-width/delimited text file assigning a type code to each boundary segment.

**Acquisition:** Download `pb2002_steps.dat` via `httpx` or manually place in `lib/`. File is small (~50 KB).

**Parsing:** The steps file format assigns each boundary segment a label and type code (CTF, CRB, CCB, OSR, OTF, OCB, SUB). Parser is ~30 lines of pure Python. Output: `lib/pb2002_types.csv` with columns `(segment_id, plate_a, plate_b, boundary_type_code, boundary_type_label, lon, lat)` as specified.

**No new dependencies required.**

---

## Dependency Summary

| REQ | New Python deps | New data files |
|---|---|---|
| REQ-1 G-K | None | None (existing algo; new subcommand) |
| REQ-1 Reasenberg | None | None |
| REQ-1 A1b-informed | None | None |
| REQ-2 | `shapely` (if Option A) | Natural Earth coastline shapefile or vertex CSV → `lib/` |
| REQ-3 | None | None (DE421 already in `lib/`) |
| REQ-4 | None | GCMT NDK files (fetched at runtime or cached in `lib/`) |
| REQ-5 | None | `pb2002_steps.dat` → `lib/` |

---

## Open Questions / Concerns

1. **REQ-1 G-K temporal window:** The current `gk_window()` formula gives significantly different temporal values than the REQ-1 lookup table for M < 6.5 (e.g., 499 days vs 915 days at M=6.0). Should the G-K variant switch to a table lookup, or is the formula considered authoritative?

2. **REQ-2 coastline approach:** Option A (`shapely` + Natural Earth) vs Option B (pure stdlib + pre-computed vertex CSV). Both are feasible. Is adding `shapely` as a runtime dependency acceptable?

3. **REQ-1 data path:** The source file is at `data/output/iscgem_global_events.csv` but REQ-1 (and REQ-3, REQ-4 outputs) reference `data/global-sets/`. Should the implementation create and populate `data/global-sets/` as a distinct directory, or treat `data/output/` as the canonical location?

4. **REQ-4 GCMT storage:** Should the raw NDK files be fetched at CLI runtime (requires internet) or downloaded once to `lib/` as a local cache? Given catalog size (~50 MB) and the offline-first design pattern of this project (DE421 stored in `lib/`), caching in `lib/` seems consistent.


## Answers to Open Questions

1. **REQ-1 G-K temporal window:** do not alter the current formula-based G-K implementation but create a new G-K varient that is table based. Make explicit in the cmd instructions/docs that this is table-based. The requirements doc appears to say that this is the authoritative table from the origional 1974 publication. This should be verified before implementation.
2. **REQ-2 coastline approach:** As this is a medium-to-low priority lets implement option b with documentation of the lighter-weight implementation that has a more robust alternative.
3. **REQ-1 data path:** treat `data/output/` as the canonical location for all data files. `data/global-sets/` should be regarded as a typo.
4. **REQ-4 GCMT storage:** Follow the offline-first design with instructions on how a user can populate `lib/` with the required files.