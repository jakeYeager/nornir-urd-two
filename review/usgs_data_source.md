# USGS Earthquake Hazards Program — FDSN Web Service

**Service:** USGS ComCat / FDSN Event Web Service
**Endpoint:** `https://earthquake.usgs.gov/fdsnws/event/1/query`
**Format returned:** CSV

## Query Parameters

| Parameter                                                    | Value / Description                                                            |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| `eventtype`                                                  | `earthquake` (hardcoded; filters out non-earthquake events like quarry blasts) |
| `catalog`                                                  | `iscgem` (hardcoded; targets catalog suited for historical event completeness) |
| `format`                                                     | `csv`                                                                          |
| `starttime` / `endtime`                                      | ISO 8601 date range (user-supplied)                                            |
| `minmagnitude` / `maxmagnitude`                              | Configurable; CLI defaults to **M6.0–6.9**                                     |
| `minlatitude`, `maxlatitude`, `minlongitude`, `maxlongitude` | Optional bounding box                                                          |

## Fields Extracted

From the raw USGS CSV response, the client parses these columns:

| USGS field  | Project field | Notes                                                                     |
| ----------- | ------------- | ------------------------------------------------------------------------- |
| `id`        | `usgs_id`     | USGS event identifier                                                     |
| `mag`       | `usgs_mag`    | Magnitude (float)                                                         |
| `time`      | `event_at`    | ISO 8601 UTC, truncated to whole seconds (sub-second precision discarded) |
| `latitude`  | `latitude`    | Decimal degrees                                                           |
| `longitude` | `longitude`   | Decimal degrees                                                           |
| `depth`     | `depth`       | Km; defaults to `0.0` if blank                                            |

## Pagination / Row Limit

The USGS API caps responses at **20,000 rows**. If a query returns exactly 20,000 rows, the client automatically splits the date range in half and recurses, merging the results. This continues until sub-ranges return fewer than 20,000 events.

## Request Timeout

HTTP requests use a **60-second timeout** via `httpx`.

---

The data source is the **USGS FDSN Event Web Service (v1)**, a standardized seismological web service operated by the USGS Earthquake Hazards Program, queried for catalogued earthquake events within a user-specified time window, magnitude range, and optional geographic bounding box.

--- 

## USGS ComCat Data Quality Notes

Unless specifically stated otherwise, data collected by this project targets the **ISC-GEM** catalog. This is to provide the most complete catalog for historical samples. [Complete rationale here](isc-gem_catalog_migration.md).

### Known ComCat Completeness Boundaries

Global ComCat datasets exhibit two well-documented record-count inflections caused by historical changes in global seismic network infrastructure — not by real changes in earthquake activity. Any dataset spanning these boundaries should be treated as non-uniform and potentially incomplete below the thresholds noted.

#### ≥M6.0 — Inflection around ~1950

The cause is the transition from the pre-WWSSN (World-Wide Standardized Seismograph Network) era to the modern instrumental era. The ISC-GEM catalog's magnitude of completeness (Mc) for shallow global events was **Mc=6.8 for 1940–1954**, only dropping to **Mc=6.5 for 1955–1963**, and **Mc=6.0 for 1964–1975**. The catalog was therefore not reliably capturing M6.0–6.8 events before the mid-1950s. The underlying driver was a postwar surge in global seismic instrumentation investment, which accelerated in the late 1950s due to nuclear test ban treaty negotiations and culminated in the deployment of the WWSSN (~120 stations in 60 countries) in the early 1960s.

**Recommended cutoff:** Use ≥M6.0 global data only from **1964** onward (full WWSSN deployment). Treat 1955–1963 as a transitional period with incomplete M6.0–6.8 coverage.

#### M4.0–5.9 — Inflection around ~1973

The cause is two compounding institutional and technical changes: (1) the NEIC (National Earthquake Information Center) was reorganized into the USGS in **1973**, significantly expanding its global monitoring mandate; and (2) global seismic networks began transitioning from analog photographic paper recordings to **digital recording through the 1970s**, which lowered detection thresholds enough to reliably capture M4–5 class events globally for the first time. The M4.0–4.5 sub-band in particular sits at the edge of global catalog completeness and is most affected.

**Recommended cutoff:** Use M4.0–5.9 global data only from **1976** onward for consistent completeness. The M4.0–4.4 sub-band should be treated with additional caution even post-1976 outside North America.

---

### Summary

| Magnitude Band    | Inflection Point | Root Cause                                           | Recommended Global Cutoff                             |
| ----------------- | ---------------- | ---------------------------------------------------- | ----------------------------------------------------- |
| ≥M6.0             | ~1950            | Pre-WWSSN era Mc=6.8; postwar network expansion      | **1964** (full WWSSN deployment)                      |
| M4.0–5.9          | ~1973            | NEIC→USGS integration + network digitization         | **1976**                                              |
| M4.0–4.4 sub-band | ~1973            | As above; sits at edge of global detection threshold | Use with caution even post-1976 outside North America |

---

*Sources: ISC-GEM Catalog Completeness Analysis (USGS, 2014); USGS NEIC History; WWSSN deployment records (USGS/ARPA, early 1960s); ANSS ComCat Documentation.*