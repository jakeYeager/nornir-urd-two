# Data Source Migration Proposal: ISC-GEM Catalog for Historical Global M≥6.0 Events

**Date:** February 25, 2026  
**Document Type:** Technical Proposal  
**Classification:** Data Architecture & Quality

---

## Executive Summary

This document proposes a targeted change to the project's data collection strategy for global M≥6.0 historical events. The proposal replaces the default USGS ComCat catalog source with the **ISC-GEM Global Instrumental Earthquake Catalogue** for the historical period (pre-2013), while retaining ComCat as the primary source for post-2013 and real-time data. The implementation cost is minimal: the project already uses the ComCat FDSN API, and the change requires only the addition of a single query parameter. The primary benefit is a substantially more complete and homogeneous dataset for the 1950–2013 window that is central to this project's long-range statistical analysis.

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [The ISC-GEM Catalog](#isc-gem-catalog)
3. [Implementation: Option 2 (ComCat API Parameter Change)](#implementation)
4. [Rationale: Two-Source Strategy](#rationale)
5. [Special Flag: WWII-Era Data Degradation (1939–1952)](#wwii-flag)
6. [Summary of Recommended Data Tiers](#summary)
7. [References](#references)


## Problem Statement

As documented in `data-source.md`, global ComCat datasets for M≥6.0 events exhibit a known record-count inflection around **~1950** — a dramatic apparent increase in events that reflects improved catalog coverage rather than real seismicity change. For long-range statistical analysis, this creates a non-uniform dataset where pre- and post-inflection records are not directly comparable.

The root cause is that ComCat aggregates raw network bulletins across contributing agencies without reprocessing them into a homogeneous standard. Magnitude types, location methods, and detection thresholds vary significantly across agencies and eras, particularly for the pre-WWSSN period (pre-1964) and the WWII disruption period (1939–1952).

Two specific problems affect M≥6.0 analysis before 2013:

- **Magnitude heterogeneity:** Pre-1976 events in ComCat use legacy magnitude scales (Ms, mb) that are not directly equivalent to the modern moment magnitude (Mw) used for post-1976 events. Cross-era comparisons conflate scale differences with real magnitude differences.
- **Catalog incompleteness:** The ComCat magnitude of completeness (Mc) for global shallow events was Mc=6.8 through 1954, meaning M6.0–6.8 events were systematically under-recorded prior to the mid-1950s.

## The ISC-GEM Catalog

The **ISC-GEM Global Instrumental Earthquake Catalogue** (International Seismological Centre / Global Earthquake Model Foundation) was purpose-built to resolve these problems for exactly this type of long-range global analysis. Key characteristics:

**Coverage:** 1904–2021 (current version: v12.1, released November 2025)  
**Magnitude threshold:** M≥5.5 globally; M≥5.0 for continental events  
**Magnitude type:** Unified Mw throughout, derived from reprocessed Ms and mb using documented empirical conversion models where direct Mw is unavailable  
**Location method:** All events relocated using the same algorithm (ISC locator) and velocity model (ak135), providing consistent hypocenter parameters with uncertainties  
**Review status:** Manually reviewed; not a real-time or automated product  
**License:** Creative Commons CC BY-SA 3.0 (attribution + share-alike)  
**DOI:** [https://doi.org/10.31905/d808b825](https://doi.org/10.31905/d808b825)

The catalog was produced by reprocessing over 100 years of instrumental seismological data — digitizing original station bulletins, recomputing surface wave and body wave magnitudes, and applying consistent relocation procedures globally. For the 1950–1963 period specifically, extension projects added pre-WWSSN events that were previously missing, significantly improving coverage for M6.0–6.8 events in that window.

For M≥6.0 global events from 1950–2013, ISC-GEM is the recognized community standard for seismic hazard and statistical seismicity research.

## Implementation: ComCat API Parameter Change

The ISC-GEM catalog is available as a named catalog contributor within the existing USGS ComCat FDSN API infrastructure. No new API client, authentication, or data pipeline changes are required. The only change is the addition of `catalog=iscgem` to the existing query parameters.

### Existing ComCat query (example)

```
https://earthquake.usgs.gov/fdsnws/event/1/query
  ?format=csv
  &starttime=1950-01-01
  &endtime=2013-01-01
  &minmagnitude=6.0
  &orderby=time
```

### Proposed ISC-GEM query (historical window)

```
https://earthquake.usgs.gov/fdsnws/event/1/query
  ?format=csv
  
  
  &starttime=1950-01-01
  &endtime=2013-01-01
  &minmagnitude=6.0
  &orderby=time
```

The response schema is identical to standard ComCat queries. The `catalog` parameter instructs ComCat to return only events where ISC-GEM is the authoritative source, filtering out the heterogeneous multi-network contributions that cause the quality issues described above.

A supplementary catalog (`iscgemsup`) is also available via `catalog=iscgemsup` and contains events that did not meet the primary catalog's quality thresholds but were still processed. This may be useful for sensitivity testing but should not be used as a primary data source.

### No code changes required beyond the query parameter

The existing collection and enrichment pipeline (including JPL DE421 astronomical enrichment via `nornir-urd-two`) can be applied to ISC-GEM records without modification, as the response format is identical.

## Rationale: Two-Source Strategy

A single catalog cannot optimally serve both historical completeness and operational recency requirements. The recommended approach is a **two-source strategy** that uses each catalog where it is strongest.

### ISC-GEM for historical events (pre-2013)

ISC-GEM is superior for the historical window because:

- **Homogeneous magnitudes:** All events carry a unified Mw value derived through documented conversion, eliminating cross-era magnitude scale artifacts in statistical analysis.
- **Consistent locations:** Uniform relocation procedure and velocity model means positional uncertainties are comparable across decades, not dependent on the methodology of whichever regional network happened to record a given event.
- **Improved pre-WWSSN completeness:** The catalog's extension projects specifically targeted the 1904–1960 gap, adding events for the 1950–1959 window that do not exist in ComCat at all.
- **Manual review:** All events are manually reviewed, reducing the automated mis-association and duplicate events that affect ComCat's older records.
- **Research standard:** ISC-GEM is the reference catalog used by the Global Earthquake Model for seismic hazard assessment and is the standard comparison dataset in published seismicity research — which supports methodological alignment with the broader literature.

The practical cutoff for switching from ISC-GEM to ComCat is **January 1, 2013**, for two reasons: (1) ISC-GEM's current version extends through 2021 but the more recent years have less review depth than the historical core; and (2) ComCat became the USGS catalog of record on January 1, 2013, meaning its coverage and quality improve significantly from that date forward.

### ComCat for post-2013 and real-time data

ComCat is superior for the modern and operational window because:

- **Near real-time availability:** USGS targets M5.0+ global events within 30 minutes, and M4.0+ U.S. events within 30 minutes. ISC-GEM is not a real-time product and has a significant lag for recent years.
- **Ongoing maintenance:** ComCat is actively maintained with event revisions in the weeks following significant earthquakes as additional phase data is incorporated.
- **Modern network coverage:** Post-2000 global network density means ComCat's completeness is substantially better at lower magnitudes than its historical record would suggest.
- **API continuity:** For any analysis requiring events up to the present day, ComCat is the only option with a consistent, maintained API.

### Transition point summary

| Period            | Recommended Source | Catalog Parameter       | Rationale                                                     |
| ----------------- | ------------------ | ----------------------- | ------------------------------------------------------------- |
| 1950–2012         | ISC-GEM            | `catalog=iscgem`        | Homogeneous Mw, manual review, extension-project completeness |
| 2013–present      | ComCat (default)   | *(no parameter needed)* | Catalog of record; real-time capable; better modern coverage  |
| Any real-time use | ComCat (default)   | *(no parameter needed)* | ISC-GEM is not a real-time product                            |


## Special Flag: WWII-Era Data Degradation (1939–1952)

Even within the ISC-GEM catalog, a known sub-period of degraded quality exists that warrants explicit flagging in the dataset and documentation.

**Affected window:** approximately **1939–1952**

The cause is wartime and immediate postwar disruption to global seismograph station operations. Station staffing, maintenance, and data transmission were severely disrupted across Europe, Asia, and parts of the Pacific from 1939 onward. Station recovery was uneven and gradual, with meaningful improvement only around 1953 when the International Seismological Summary (ISS) began receiving significantly more station contributions.

The ISC-GEM documentation notes this explicitly: the annual number of events per year in this window is lower than neighboring periods not because fewer earthquakes occurred, but because fewer were detected and catalogued. The 1940s in particular show a dip in coverage even after ISC-GEM's extension project work, as the source data simply does not exist for many events that would otherwise meet the M≥6.0 threshold.

### Recommended implementation

Add a boolean flag `wartime_data_quality_flag` (or equivalent) to any record with an origin date in the range **1939-09-01 through 1952-12-31**. This flag should propagate to any derived analysis outputs and be noted in statistical summaries that include this period.

```
wartime_data_quality_flag = (year >= 1939 AND month >= 9) AND (year <= 1952)
```

Analysis using this window should note that event counts in this period are likely an undercount of true M≥6.0 activity, and cross-period rate comparisons that include this window should treat it as a lower-bound estimate.


## Summary of Recommended Data Tiers

| Tier                  | Date Range   | Source  | Catalog Param    | Quality Notes                                                   |
| --------------------- | ------------ | ------- | ---------------- | --------------------------------------------------------------- |
| 1 — Pre-war           | 1950–1938    | ISC-GEM | `catalog=iscgem` | Best available; Mc~6.5 improving toward 6.0 by 1955             |
| 2 — WWII degraded     | 1939–1952    | ISC-GEM | `catalog=iscgem` | Apply `wartime_data_quality_flag`; event counts are undercounts |
| 3 — WWSSN transition  | 1953–1963    | ISC-GEM | `catalog=iscgem` | Improving coverage; treat M6.0–6.5 as potentially incomplete    |
| 4 — Modern historical | 1964–2012    | ISC-GEM | `catalog=iscgem` | Full WWSSN+ coverage; Mc≤6.0; highest confidence tier           |
| 5 — ComCat era        | 2013–present | ComCat  | *(default)*      | Catalog of record; real-time capable                            |


## References

- International Seismological Centre (2025). ISC-GEM Earthquake Catalogue, v12.1. [https://doi.org/10.31905/d808b825](https://doi.org/10.31905/d808b825)
- Di Giacomo, D. et al. (2018). The ISC-GEM Earthquake Catalogue (1904–2014): status after the Extension Project. *Earth System Science Data*, 10, 1877–1899. [https://essd.copernicus.org/articles/10/1877/2018/](https://essd.copernicus.org/articles/10/1877/2018/)
- Michael, A.J. (2014). How Complete is the ISC-GEM Global Earthquake Catalog? *Bulletin of the Seismological Society of America*, 104(4), 1829–1837.
- USGS ANSS ComCat Documentation. [https://earthquake.usgs.gov/data/comcat/](https://earthquake.usgs.gov/data/comcat/)
- USGS ComCat Catalog Registry — ISCGEM entry. [https://earthquake.usgs.gov/data/comcat/catalog/iscgem/](https://earthquake.usgs.gov/data/comcat/catalog/iscgem/)
- USGS National Earthquake Information Center (NEIC). [https://www.usgs.gov/programs/earthquake-hazards/national-earthquake-information-center-neic](https://www.usgs.gov/programs/earthquake-hazards/national-earthquake-information-center-neic)

---

**Document Version:** 1.0  
**Generated with:** Claude Sonnet 4.6 — Claude.ai Web Interface
