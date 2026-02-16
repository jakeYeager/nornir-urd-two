# Decision: OpenQuake Engine Not Adopted

## Context

During external analysis of data collected by this project, a reference to `openquake.hmtk` (the Hazard Modeller's Toolkit, part of the OpenQuake Engine) was encountered as a potential tool for Gardner-Knopoff declustering. This document records the research and rationale for implementing the algorithm ourselves instead.

## What was evaluated

- `openquake.hmtk.seismicity.decluster.dec_gardner_knopoff.GardnerKnopoffType1` -- the specific declustering function recommended
- Other hmtk modules: completeness (Stepp 1971), recurrence (Gutenberg-Richter b-value), smoothed seismicity, catalog parsers (ISC-GEM, GCMT)
- The full OpenQuake Engine dependency footprint

## Why we did not adopt OpenQuake

### 1. hmtk is not standalone

`openquake.hmtk` is a subpackage of `openquake-engine`. There is no `pip install openquake-hmtk`. Installing it brings the full hazard calculation engine, including:

- **django** -- web framework for the Engine's WebUI
- **h5py** -- HDF5 I/O for hazard calculation results
- **scipy**, **shapely**, **pyproj** -- scientific/geospatial libraries
- **pyzmq** -- messaging infrastructure
- **pandas** -- dataframes
- Plus ~20 transitive dependencies

Our project has two runtime dependencies (`httpx`, `skyfield`). Adding OpenQuake would increase the dependency surface by an order of magnitude for a single function call.

### 2. The algorithm is simple

The Gardner-Knopoff (1974) declustering algorithm is well-documented in the seismology literature and straightforward to implement:

1. For each event, compute a magnitude-dependent spatial radius and temporal window using the G-K 1974 empirical formulas
2. Process events by descending magnitude
3. Flag smaller events within the space-time window as dependent (aftershock/foreshock)
4. Remaining events are mainshocks

Our implementation (`nornir_urd/decluster.py`) is ~100 lines of pure Python with no new dependencies. It uses the Haversine formula for great-circle distances and the original G-K 1974 empirical window formulas:

- Distance: `d = 10^(0.1238 * M + 0.983)` km
- Time (M < 6.5): `t = 10^(0.5409 * M - 0.547)` days
- Time (M >= 6.5): `t = 10^(0.032 * M + 2.7389)` days

### 3. AGPL-3.0 license implications

OpenQuake Engine is licensed under AGPL-3.0. Vendoring just the declustering code would require license compliance considerations. Implementing from the published algorithm avoids this entirely.

### 4. Our catalog size is small

For M6.0+ global events, the USGS catalog yields ~100-200 events per year. Pure-Python O(n^2) pairwise comparison is more than sufficient at this scale. Vectorized numpy operations (which OpenQuake uses internally) provide no meaningful performance benefit.

## What we kept from the research

- **Catalog parsers as reference**: If we later want to integrate ISC-GEM or GCMT catalogs for historical depth, the hmtk parser formats serve as a useful schema reference.
- **Completeness analysis**: Stepp (1971) completeness analysis could be valuable in the future. The algorithm is also straightforward to implement independently if needed.
- **Algorithm validation**: The OpenQuake implementation served as a reference for verifying our G-K window formulas match the original 1974 paper.

## Full research

See [review/03_plan_review.md](03_plan_review.md) for the complete evaluation including hmtk feature inventory, catalog comparison table, and dependency analysis.
