# Plan 03 Review: OpenQuake hmtk Integration for Declustering

## 1. Can we implement `openquake.hmtk` and use Gardner-Knopoff declustering?

**Yes, but with caveats.**

### What the function expects

`GardnerKnopoffType1()` (the class in `openquake.hmtk.seismicity.decluster.dec_gardner_knopoff`) operates on an `openquake.hmtk.seismicity.catalogue.Catalogue` object. This is a dict-like container requiring NumPy arrays for at minimum:

| Key         | Type         | Description      |
| ----------- | ------------ | ---------------- |
| `longitude` | `np.ndarray` | Event longitudes |
| `latitude`  | `np.ndarray` | Event latitudes  |
| `magnitude` | `np.ndarray` | Event magnitudes |
| `year`      | `np.ndarray` | Integer years    |
| `month`     | `np.ndarray` | Integer months   |
| `day`       | `np.ndarray` | Integer days     |
| `hour`      | `np.ndarray` | Integer hours    |
| `minute`    | `np.ndarray` | Integer minutes  |
| `second`    | `np.ndarray` | Float seconds    |

The method returns:
- `vcl` -- cluster index vector (0 = mainshock / unclustered, >0 = cluster ID)
- `vmain_shock` -- boolean flag array identifying mainshocks

### What we need to change

1. **Add `latitude` to CSV output.** The USGS API already returns latitude in its response -- we just don't extract it in `_parse_rows()`. This is a one-line fix in `usgs.py` and a column addition in `cli.py`.

2. **Build an hmtk `Catalogue` from our data.** We'd parse our enriched event list into the NumPy arrays above. This is straightforward since we already have `event_at` (ISO timestamp), `usgs_mag`, `longitude`, and (soon) `latitude`.

3. **Configure the window function.** Gardner-Knopoff uses `GardnerKnopoffWindowOrig()` for the standard 1974 lookup tables. Pass this as the `config['window_opt']` parameter.

### Minimal integration example

```python
from openquake.hmtk.seismicity.catalogue import Catalogue
from openquake.hmtk.seismicity.decluster.dec_gardner_knopoff import GardnerKnopoffType1
from openquake.hmtk.seismicity.decluster.distance_time_windows import GardnerKnopoffWindowOrig

catalogue = Catalogue()
catalogue.data = {
    'longitude': lon_array,
    'latitude': lat_array,
    'magnitude': mag_array,
    'year': year_array,
    'month': month_array,
    'day': day_array,
    'hour': hour_array,
    'minute': minute_array,
    'second': second_array,
}
catalogue.end_year = int(year_array.max())
catalogue.start_year = int(year_array.min())

decluster = GardnerKnopoffType1()
config = {
    'time_distance_window': GardnerKnopoffWindowOrig(),
    'fs_time_prop': 1.0,  # foreshock time proportion (1.0 = symmetric)
}
vcl, vmain = decluster.decluster(catalogue, config)
```

**Verdict: Yes, this is implementable.** The main work is (a) adding latitude and (b) writing a thin adapter to convert our event dicts into an hmtk `Catalogue`.

---

## 2. Other useful hmtk features

### Relevant to this project

| Module                           | Feature                                                  | Value to us                                                                                  |
| -------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `seismicity.decluster`           | Gardner-Knopoff, Afteran, and other declustering methods | Direct need -- the primary motivation                                                        |
| `seismicity.completeness`        | Stepp (1971) completeness analysis                       | Useful for determining magnitude-completeness thresholds before analysis                     |
| `seismicity.occurrence`          | Gutenberg-Richter b-value estimation (Aki, Weichert)     | Could validate whether our magnitude bands follow expected frequency distributions           |
| `seismicity.max_magnitude`       | Maximum magnitude estimators (Kijko, cumulative moment)  | Not directly needed but available                                                            |
| `seismicity.smoothed_seismicity` | Kernel-smoothed seismicity rates                         | Potentially useful for spatial analysis but not required for the current Cases 1-4B approach |
| `parsers`                        | ISC, GCMT, and CSV catalog parsers                       | See section 3 below                                                                          |

### Not relevant

The full hmtk also includes source model tools (fault geometry, area sources, MFD assignment) that are for PSHA and not applicable to our temporal clustering analysis.

**Verdict: Completeness analysis and b-value estimation are the most useful extras.** Smoothed seismicity could be a future enhancement but is not needed now.

---

## 3. Access to larger catalogs

### What hmtk provides

hmtk includes **parsers** for catalog formats, not the catalogs themselves:

- **ISC (International Seismological Centre)** -- `parsers.catalogue.csv.CsvCatalogueParser` and ISC-specific parsers. The ISC Bulletin and ISC-GEM catalog are the most comprehensive global catalogs, going back to 1900 (ISC-GEM) or 1964 (ISC reviewed).
- **GCMT (Global Centroid Moment Tensor)** -- `parsers.catalogue.gcmt_ndk_parser`. Provides moment tensors and centroid locations from ~1976 onward for M >= ~5.0.
- **Generic CSV** -- any catalog can be loaded if reformatted to hmtk's CSV schema.

### Catalogs worth considering

| Catalog               | Coverage     | Magnitude threshold        | Advantage over USGS                                 |
| --------------------- | ------------ | -------------------------- | --------------------------------------------------- |
| ISC-GEM               | 1900-present | ~5.5+ (varies by era)      | Longer historical record, reviewed/relocated events |
| ISC Bulletin          | 1964-present | ~3.5+ (varies by region)   | More events, multiple agency solutions              |
| GCMT                  | 1976-present | ~5.0+                      | Moment magnitudes, focal mechanisms                 |
| USGS ComCat (current) | 1900-present | ~2.5+ (US), ~4.5+ (global) | Already integrated, real-time                       |

**Verdict: The ISC-GEM catalog would be the most valuable addition** for historical depth. However, these catalogs require manual download (they're not available via the same kind of real-time API as USGS ComCat). For our current use case (M6.0-6.9 global events), the USGS catalog is sufficient. Supplementary catalogs become important if we want to extend the time range before ~1970 or validate completeness.

---

## 4. OpenQuake Engine vs. hmtk-only: bloat assessment

### The problem

**hmtk is not a standalone package.** It is a subpackage of `openquake-engine`. You cannot `pip install openquake.hmtk` -- you must install `openquake.engine`, which brings the full hazard calculation engine.

### Dependency footprint of `openquake-engine`

Core dependencies include:
- `numpy`, `scipy` -- already common, reasonable
- `h5py` -- HDF5 file I/O (the engine's native storage format)
- `django` -- yes, the web framework, used for the engine's WebUI and database
- `shapely` -- geometric operations
- `pyproj` -- coordinate transformations
- `toml`, `requests`, `pyzmq` -- configuration, HTTP, messaging
- `pandas` -- dataframes (we don't currently use this)
- Plus various other engine-specific dependencies

**This is significant bloat.** Our current dependency list is `httpx` + `skyfield`. Adding `openquake-engine` would pull in Django, h5py, scipy, shapely, pyzmq, and ~20+ transitive dependencies for a project that only needs one function from one submodule.

### Python version

OpenQuake Engine requires **Python >= 3.9** (compatible with our project), but the dependency weight remains the primary concern, not version compatibility.

### Alternative: implement Gardner-Knopoff ourselves

The Gardner-Knopoff algorithm is straightforward (~80 lines of core logic):

1. Sort events by magnitude (descending)
2. For each event, compute space-time windows from the G-K 1974 lookup table
3. Flag smaller events within the window as aftershocks
4. Remaining unflagged events are mainshocks

The distance calculation (Haversine) is ~10 lines. The lookup table is a small dict. Total implementation: **~100-150 lines** with no new dependencies beyond what we already have (or optionally adding `numpy` for vectorized distance computation).

### Recommendation

| Option                                        | Pros                                                                    | Cons                                                                                                     |
| --------------------------------------------- | ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| **A: Install openquake-engine**               | Battle-tested, multiple algorithms, catalog parsers                     | Massive dependency bloat (Django, h5py, scipy, etc.), Python >=3.10, install can be slow/fragile         |
| **B: Implement G-K ourselves**                | Zero new dependencies, full control, small codebase, keeps Python >=3.9 | Must write and test ~150 lines, only one algorithm                                                       |
| **C: Vendor just the hmtk declustering code** | No Django/engine bloat, proven algorithm                                | License compliance (AGPL-3.0), must track upstream changes, still need numpy+scipy for distance matrices |

**Verdict: Option B (implement ourselves) is the strongest fit for this project.** The algorithm is well-documented in the literature, our codebase values minimal dependencies, and the implementation is small. If we later need completeness analysis or b-value estimation, we can revisit.

---

## 5. Implementation plan (if proceeding with Option B)

### Phase 1: Add latitude to pipeline
1. Extract `latitude` in `usgs.py:_parse_rows()` (already available in USGS response)
2. Add `latitude` to `OUTPUT_COLUMNS` in `cli.py`
3. Thread `latitude` through `_enrich()`
4. Update tests

### Phase 2: Implement Gardner-Knopoff declustering
1. Create `nornir_urd/decluster.py` with:
   - Haversine distance function
   - Gardner-Knopoff 1974 window lookup table
   - `decluster_gardner_knopoff(events) -> (mainshocks, aftershocks)` function
2. Add tests against known catalog subsets
3. Add `decluster` CLI subcommand (input CSV -> two output CSVs)

### Phase 3: Integration
1. Run declustering on `global_events.csv` (after latitude augmentation)
2. Produce `mainshocks.csv` and `aftershocks.csv`
3. Re-run Cases 1-4B analysis on the mainshock catalog

### Phase 4: Documentation
1. Make a document `no_open_quake.md` and document our research and reason for not implementing OpenQuake in this project. Also update the `.claude/CLAUDE.md` with appropriate context of this decision
2. Update `README.md` Usage section with instructions and examples of how to use the `decluster` subcommand. 
   1. If it is possible to decluster existing CSVs list the header requirements and steps
   2. List any limitations to the raw calculation accuracy of our implemenation (if any exist)
---

## Open questions for review

1. **Should latitude appear before or after longitude in the CSV column order?** Convention is `lat, lon` but our current schema has `longitude` last. Suggest inserting `latitude` immediately before `longitude`.

2. **Do we want a `--decluster` flag on the `collect` command, or a separate `decluster` subcommand?** A separate subcommand is cleaner (separation of concerns: collection vs. analysis).

3. **Should we add `numpy` as a dependency for vectorized Haversine?** Pure-Python Haversine is fine for catalogs under ~50k events. For M6.0+ global catalogs (~100-200 events/year), pure Python is more than sufficient. Recommend: no new dependencies.

4. **Do we want to backfill latitude for already-collected CSVs?** This would require re-fetching from USGS by event ID, or a one-time augmentation script.

---

## Answers to open review questions

1. No preference for downstream effects. Please also include `depth` while we are making changes to event coordinates.
2. Yes make a separate subcommand. If it allows for an `--input` arg then it could be used to decluster existing CSVs (provided they have `event_at`, `latitude`, and `longitude` headers). Please see Phase 4 for documentation tasks
3. Pure-Python is fine. Less overhead is better if we can can still maintain accuracy. Please see Phase 4 for documentation tasks
4. No need. New CSVs for testing is ok