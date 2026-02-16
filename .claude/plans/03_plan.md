In the analysis I am implementing else where with data collected from this project I came across a reference to `openquake.hmtk` and OpenQuake Engine. Can you make me an implementation plan (with any questions) at review/03_plan_review.md that covers:

- Can we implement `openquake.hmtk` in this project and use
`openquake.hmtk.seismicity.decluster.gardner_knopoff_decluster()` once we include `latitude` in our CSV output?
- Are there other features of the library that would streamline or enhance our current implementation?
- Is there access to other bigger catalogs of events not available via the USGS API?
- OpenQuake Engine a better solution (`openquake.hmtk` is included) or are we introducing bloat?

The following was the recommended implementation to decluster the data for further analysis:

**Method: Gardner-Knopoff Windowing**
The Gardner-Knopoff (1974) declustering algorithm separates mainshocks from aftershocks using magnitude-dependent space-time windows. For each event, a spatial radius and temporal window are defined based on its magnitude (e.g., M6.0 ≈ 40 km / 22 days; M7.0 ≈ 150 km / 64 days). Any smaller event falling within a larger event's window is classified as an aftershock. The remaining events form the "declustered" background catalog.

**Prerequisites:**
1. **Latitude column required:** The current `global_events.csv` contains `longitude` but not `latitude`. Spatial windowing requires both coordinates for inter-event distance calculation. The latitude data must be added from the USGS source catalog.
2. **Distance calculation:** Haversine or Vincenty formula for great-circle distances between event pairs.
3. **Window parameters:** Gardner & Knopoff (1974) published standard magnitude-dependent lookup tables for spatial radius (km) and temporal window (days).

**Implementation Outline:**
1. Augment `global_events.csv` with `latitude` column from USGS source data
2. Implement Gardner-Knopoff algorithm (or leverage `openquake.hmtk` library)
3. Produce two derived catalogs: mainshocks-only and aftershocks-only
4. Re-run the Approach Three analysis suite (Cases 1–4B) on the declustered mainshock catalog
5. Compare clustering signal strength before/after declustering