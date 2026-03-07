An external data analysis project has some specific requirements in adding additional attributes to collected results. These are broken up into 5 different analysis cases within a topic.

**Tasks & Outputs**
1. The first task is a feasibility study to ensure that of all the required libs, tools and/or resources needed can be obtained and integrated into this data pipeline project. All questions and concerns will be address between you and the user before moving on to second task.
   1. The feasibility study will be documented here for review: `.claude/plans/06_feasibility.md` .
2. The second task is creating a phased implementation plan, where each phase handles a single cases' requirements, in sequence of the case priority. On matching priority defer to "REQ" numbering. Each phase should be self-contained and not require any other phase implementation to be completed first.
   1. All subcommands should be unique and options and args instructions
   2. In REQ-2 all 3 options are desirable; the PB2002 file has already been sourced and is located at `lib/pb2002_boundaries.dig`
   3. The phased implementation study will be documented here for review: `.claude/plans/06_phases.md` .

Read the following case requirements to build the feasibility study and phased plan:

---

# Topic A2 Data Requirements

Identifies all data inputs required by Topic A2 cases that are not currently present in the project. Requirements are separated by type: **computed pipeline outputs** (derived from existing data or algorithms) and **external acquisitions** (new data sources to obtain). Analysis-time derivations (hemisphere from latitude, depth band from depth, magnitude band from usgs_mag) are not listed — those require no pipeline work.

Implementation priority follows the case execution order: A4 → B6 → A1 → B1 → A3 → B2 → B4 → A2 → B3 → B5.

---

## Computed Pipeline Outputs

### REQ-1: ISC-GEM Declustered Catalogs

**Required by:** A4 (execute first), A1 (after A4), B6 (uses raw catalog only — no dependency)

**Priority:** Critical — A4 is a prerequisite for all downstream cases

**Description:** Three independent declustering runs applied to `data/global-sets/iscgem_global_events.csv` (n=9,210). Each run produces a mainshock file (retained events) and an aftershock file (removed events). Currently only ComCat is declustered (`data/declustering/comcat_mainshocks.csv`, `comcat_aftershocks.csv`).

**Three variants required:**

| Variant | Method | Spatial window | Temporal window |
| --- | --- | --- | --- |
| G-K | Gardner-Knopoff (1974) | Magnitude-scaled (standard table) | Magnitude-scaled (standard table) |
| Reasenberg | Reasenberg (1985) | Interaction radius, magnitude-dependent | Lookback window, adaptive |
| A1b-informed | Custom (data-derived) | 83.2 km (fixed) | 95.6 days (fixed) |

**G-K standard window table (Gardner & Knopoff 1974):**

| M range | Spatial (km) | Temporal (days) |
| --- | --- | --- |
| ≥ 2.5 | 19.5 | 22 |
| ≥ 3.0 | 22.5 | 42 |
| ≥ 3.5 | 26.0 | 83 |
| ≥ 4.0 | 30.0 | 155 |
| ≥ 4.5 | 35.0 | 290 |
| ≥ 5.0 | 40.0 | 510 |
| ≥ 5.5 | 47.0 | 790 |
| ≥ 6.0 | 54.0 | 915 |
| ≥ 6.5 | 61.0 | 960 |
| ≥ 7.0 | 70.0 | 985 |

Note: Some published G-K tables use 49 km / 295 days for M6.0 (rounded). Use the above values from the 1974 paper directly.

**Reasenberg (1985) parameters:** Use published defaults — interaction radius r_fact=10 (10× location uncertainty), tau_min=1 day, tau_max=10 days, p=0.95, xmeff=1.5 (effective magnitude threshold). Apply the ZMAP or equivalent implementation.

**A1b-informed custom window:** Fixed spatial radius 83.2 km and fixed temporal window 95.6 days for all magnitudes. Apply as a simple circle-and-window method: for each event (descending magnitude), designate as aftershock any subsequent event within 83.2 km and 95.6 days of a higher-magnitude event not already designated as aftershock.

**Output file locations:**

```
data/declustering/iscgem_gk_mainshocks.csv
data/declustering/iscgem_gk_aftershocks.csv
data/declustering/iscgem_reasenberg_mainshocks.csv
data/declustering/iscgem_reasenberg_aftershocks.csv
data/declustering/iscgem_a1b_mainshocks.csv
data/declustering/iscgem_a1b_aftershocks.csv
```

**Schema:** Same as source — `usgs_id, usgs_mag, event_at, solaration_year, solar_secs, lunar_secs, midnight_secs, latitude, longitude, depth`. No new columns required; the mainshock/aftershock split is conveyed by file membership.

---

### REQ-2: Ocean/Continent Classification Column

**Required by:** B2

**Priority:** Medium (B2 is 6th in execution order)

**Description:** A derived column classifying each ISC-GEM event's geographic context. The planning doc specifies a distance-to-coastline approach.

**Classification scheme:**

| Class | Criterion | Label |
| --- | --- | --- |
| Oceanic | > 200 km from nearest coastline | `oceanic` |
| Continental | On land or < 50 km offshore | `continental` |
| Transitional | 50–200 km from coastline | `transitional` |

**Implementation options (in preference order):**

1. **Natural Earth coastline** (`ne_110m_coastline` or `ne_10m_coastline` shapefiles) — compute minimum Haversine distance from each event to the nearest coastline vertex. Widely available and Python-compatible via `shapely` / `geopandas`.

2. **GSHHG (Global Self-consistent Hierarchical High-resolution Geography)** — higher resolution than Natural Earth; same approach. Available at https://www.ngdc.noaa.gov/mgg/shorelines/

3. **PB2002 as a coarse proxy** — not recommended; plate boundaries do not align with coastlines. Use only as a fallback if coastline data cannot be sourced.

**Output:** Add `ocean_class` column (values: `oceanic`, `continental`, `transitional`) to an enriched ISC-GEM file, or produce a standalone join file:

```
data/global-sets/iscgem_ocean_class.csv   (usgs_id, ocean_class, dist_to_coast_km)
```

---

### REQ-3: Solar Declination and Earth-Sun Distance Columns

**Required by:** B5

**Priority:** Low (B5 is last in execution order)

**Description:** Three new ephemeris-derived columns per event, computed using Skyfield 1.54 with JPL DE421 (already used for `solar_secs`, `lunar_secs`, `midnight_secs` in the existing pipeline via the nornir-urd-two collection tool).

**New columns:**

| Column | Description | Units | Range |
| --- | --- | --- | --- |
| `solar_declination` | Solar declination angle at event time | Degrees | −23.5 to +23.5 |
| `declination_rate` | Rate of change of solar declination at event time | Degrees/day | ~−0.40 to +0.40 |
| `earth_sun_distance` | Earth-Sun distance at event time | AU | ~0.983 to ~1.017 |

**Implementation:** Extend the existing ephemeris computation in nornir-urd-two to output these three additional values per event. At each `event_at` UTC timestamp:
- `solar_declination`: solar ecliptic latitude converted to equatorial declination via Skyfield's sun position
- `declination_rate`: finite difference of `solar_declination` over ±0.5 days at event time
- `earth_sun_distance`: Earth-Sun distance from Skyfield ephemeris

**Output:** Add columns to an enriched ISC-GEM file, or produce a standalone join file:

```
data/global-sets/iscgem_solar_geometry.csv   (usgs_id, solar_declination, declination_rate, earth_sun_distance)
```

---

## External Acquisitions

### REQ-4: GCMT Focal Mechanism Catalog

**Required by:** B3

**Priority:** Medium (B3 is 9th in execution order)

**Description:** The Global Centroid Moment Tensor (GCMT) catalog provides focal mechanism type for each earthquake. Required to classify ISC-GEM events as thrust, normal, or strike-slip for tectonic regime stratification.

**Source:** https://www.globalcmt.org/CMTfiles.html

**Coverage needed:** Global, M ≥ 6.0, 1950–2021. GCMT catalog begins in 1976 — pre-1976 ISC-GEM events will have no focal mechanism match.

**Format:** GCMT provides NDK format (fixed-width text) and period-based text files. A pre-parsed CSV version is available from several academic mirrors.

**Join strategy:** Match GCMT events to ISC-GEM events using spatial-temporal proximity — same tolerances as Case A0b cross-catalog matching (±60s, 50 km, ±0.3 magnitude). One-to-one matching; unmatched ISC-GEM events (primarily pre-1976) receive `mechanism = null`.

**Focal mechanism classification from moment tensor:**
- Extract rake angle from the preferred nodal plane
- `thrust`: rake in [45°, 135°]
- `normal`: rake in [−135°, −45°]
- `strike_slip`: rake in (−45°, 45°] or (135°, 180°] / [−180°, −135°)
- Mixed mechanisms (oblique): classify by dominant component or flag as `oblique`

**Output:**

```
data/global-sets/iscgem_focal_mechanisms.csv   (usgs_id, gcmt_id, mechanism, rake, strike, dip, scalar_moment, centroid_depth, match_confidence)
```

Where `match_confidence` is `exact_id` (if GCMT event ID matches), `proximity` (matched by time/location), or `null` (no match found).

---

### REQ-5: PB2002 Boundary Type Classification

**Required by:** B3 (fallback proxy for tectonic regime if GCMT unavailable), B2 (supplement to ocean/continent classification)

**Priority:** Medium — dependency on B3 and B2

**Description:** The `lib/pb2002_boundaries.dig` file contains plate boundary coordinates but not explicit boundary type codes. The PB2002 dataset includes a supplementary steps file (`pb2002_steps.dat`) that assigns each boundary segment a type code.

**PB2002 boundary type codes (Bird 2003):**

| Code | Description | Seismic relevance |
| --- | --- | --- |
| CTF | Continental transform fault | Strike-slip dominant |
| CRB | Continental rift boundary | Normal dominant |
| CCB | Continental convergent boundary | Thrust dominant |
| OSR | Oceanic spreading ridge | Normal dominant |
| OTF | Oceanic transform fault | Strike-slip dominant |
| OCB | Oceanic convergent boundary | Thrust dominant |
| SUB | Subduction zone | Thrust dominant |

**Source:** Peter Bird's PB2002 supplementary data. The steps file is available at the same source as the boundaries file: https://peterbird.name/publications/2003_PB2002/2003_PB2002.htm

**Acquisition:** Download `pb2002_steps.dat` and place in `lib/`. Parse to produce a boundary-segment-to-type lookup.

**Output:** A parsed reference file:

```
lib/pb2002_types.csv   (segment_id, plate_a, plate_b, boundary_type_code, boundary_type_label, lon, lat)
```

Usable by analysis scripts for nearest-boundary-type classification of any event.

---

## Summary Table

| ID | Requirement | Type | Cases | Priority | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-1 | ISC-GEM declustered catalogs (3 variants) | Computed | A4, A1 | Critical | Not started |
| REQ-2 | Ocean/continent classification | Computed | B2 | Medium | Not started |
| REQ-3 | Solar declination / Earth-Sun distance columns | Computed | B5 | Low | Not started |
| REQ-4 | GCMT focal mechanism catalog | External acquisition | B3 | Medium | Not started |
| REQ-5 | PB2002 boundary type classification | External acquisition | B3 (fallback), B2 (supplement) | Medium | Not started |

**Not required from pipeline** (derivable at analysis time from existing schema):
- Hemisphere split (`latitude > 0` / `< 0`) — B1
- Depth stratification bands (from `depth`) — B4
- Magnitude stratification bands (from `usgs_mag`) — A2, A3
- Phase normalization (from `solar_secs`, `lunar_secs`, `midnight_secs` + cycle constants) — all cases
