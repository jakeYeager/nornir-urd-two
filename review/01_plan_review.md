# Implementation Plan Review

## Phase 1 - Astronomical Calculations

### Library Assessment: PyEphem vs Alternatives

**PyEphem CAN provide all required calculations** (solstices, equinoxes, new moons for 1948-2050). However, there is an important consideration:

**PyEphem is deprecated.** Its author (Brandon Rhodes) replaced it with **Skyfield**, which is actively maintained, more accurate, and has a cleaner API. Both libraries support the required date range.

| Capability             | PyEphem                             | Skyfield                                       |
| ---------------------- | ----------------------------------- | ---------------------------------------------- |
| Solstice/equinox times | `next_solstice()`, `next_equinox()` | `almanac.seasons()` with `find_discrete()`     |
| New moon times         | `next_new_moon()`                   | `almanac.moon_phases()` with `find_discrete()` |
| Date range 1948-2050   | Supported                           | Supported (DE421 ephemeris covers 1900-2050)   |
| Accuracy               | ~1 arcsecond (VSOP87)               | Sub-arcsecond (NASA JPL ephemerides)           |
| Maintenance            | No longer developed                 | Actively maintained                            |

**Recommendation:** Use **Skyfield** with the DE421 ephemeris file (~17 MB). It is the modern successor to PyEphem by the same author, with better accuracy and ongoing support.

> **QUESTION 1:** Should we proceed with Skyfield instead of PyEphem? Or is there a specific reason to stick with PyEphem (e.g., matching legacy results exactly)?

> **Answer 1:** Please use Skyfield instead of PyEphem. That sounds like a good choice.

### Proposed Calculation Implementations

**1. Solaration (`solar_secs`)**
- Pre-compute all December solstice (winter/hibernal) timestamps from 1948-12-21 through 2050-12-21 using ephemeris data
- For each event: find the most recent December solstice before `event_at`, compute `event_at - solstice_timestamp` in seconds
- Store `solaration_year` as the year of the *next* December solstice (matching legacy convention where a Dec 25, 1949 event has `solaration_year=1950`)

**2. Lunation (`lunar_secs`)**
- Pre-compute all new moon timestamps from 1948-12-01 through 2050-12-31
- For each event: find the most recent new moon before `event_at`, compute `event_at - new_moon_timestamp` in seconds

**3. Midnight (`midnight_secs`)**
- Translation of the legacy Ruby logic into Python:

```python
def midnight_secs(event_at: datetime, longitude: float) -> int:
    seconds_from_utc = int(longitude / (360.0 / 86400))
    time_at_longitude = event_at + timedelta(seconds=seconds_from_utc)
    midnight = time_at_longitude.replace(hour=0, minute=0, second=0, microsecond=0)
    return int((time_at_longitude - midnight).total_seconds())
```

- This produces seconds elapsed since local solar midnight at the event's longitude
- Range: 0 to 86399

> **QUESTION 2:** The `midnight_secs` calculation uses `int()` truncation (matching Ruby's `.to_i`). The legacy code also truncates `seconds_from_utc`. Should we match this truncation behavior exactly, or would rounding be preferred for new data?

> **Answer 2:** No need to match exactly. `.to_i` was used to force null values to 0 in Ruby (if null occured). Whole second integers is expected.

### Proposed Module Structure

```
nornir_urd/
├── __init__.py
├── astro.py            # Solstice, new moon pre-computation; solar_secs, lunar_secs, midnight_secs
├── usgs.py             # USGS API client (Phase 3)
├── validate.py         # Legacy data comparison (Phase 2)
└── cli.py              # Command-line entry point
```

> **QUESTION 3:** Is a flat module structure acceptable, or do you prefer a different organization (e.g., separate packages per phase)?

> **Answer 3:** Please move the Phase 2 validation into its own temporary dir. It will be removed once we complete testing the legacy data.
 
---

## Phase 2 - Legacy Data Validation

### Legacy Data Summary
- **10,105 records** spanning 1949-12-25 to 2021-12-20
- **Columns:** `usgs_id, usgs_mag, event_at, solaration_year, solar_secs, lunar_secs, midnight_secs, longitude`
- Magnitudes range from 6.0+

### Validation Strategy

**`solar_secs` - Expected to differ**
- Legacy used `YYYY/12/21T00:00:00Z` as approximate solstice times
- Ephemeris-based solstice times will produce different values
- Plan: compute new values, report deltas, and provide a summary of differences (min/max/mean/median offset)

**`lunar_secs` - Expected to be close**
- Legacy attempted to use exact new moon timestamps
- Plan: compute new values, flag any records where delta exceeds a threshold (e.g., > 60 seconds)
- Investigate deficit pattern mentioned in plan notes

**`midnight_secs` - Needs careful validation**
- Plan: re-implement the exact Ruby logic in Python, verify output matches legacy values exactly
- If mismatches found: analyze whether they are systematic (rounding, off-by-one) or data-specific

### Validation Output
- A comparison CSV with columns: `usgs_id, event_at, legacy_solar_secs, new_solar_secs, solar_delta, legacy_lunar_secs, new_lunar_secs, lunar_delta, legacy_midnight_secs, new_midnight_secs, midnight_delta`
- A summary report with statistics on each delta column saved to review/legacy_data_report.md

> **QUESTION 4:** For `solar_secs` validation, since we know the legacy values used approximate solstice times, should we also compute values using `YYYY/12/21T00:00:00Z` to verify our logic matches the legacy approach before switching to ephemeris-based values?

> **Answer 4:** No, please use the ephemeris-based values. The report deltas would be informative. It is a simple enough computation that vast differences would be suspicious. I am more concerned with midnight_secs and getting an accurate value for the how many seconds have elapsed since local midnight at the earthquake's location!

---

## Phase 3 - New Data Collection

### USGS API Details
- **Endpoint:** `https://earthquake.usgs.gov/fdsnws/event/1/query`
- **Format:** CSV (22 columns returned, we need 4: `id`, `mag`, `time`, `longitude`)
- **Limit:** 20,000 events per query (pagination via `offset` parameter)

### Proposed CLI Interface

```bash
# With defaults (all params optional)
python -m nornir_urd collect --output events.csv

# With custom parameters
python -m nornir_urd collect \
  --start 2020-01-01 --end 2025-12-31 \
  --min-mag 5.0 --max-mag 9.0 \
  --min-lat -90 --max-lat 90 \
  --min-lon -180 --max-lon 180 \
  --output events.csv
```

### Proposed Default Parameters

> **QUESTION 5:** What should the default search parameters be? Some suggestions:
> - **Magnitude:** min 6.0 (matching legacy data which appears to be 6.0+)
> - **Date range:** What default start/end dates?
> - **Geography:** Global (no lat/lon restrictions)?

> **Answer 5:** Default parameters
> - min-mag: 6.0 & max-mag: 6.9
> - start [today - 5 days] & end [today]
> - Global (no default values)

### Output CSV Format

The output CSV will match the legacy format with corrected astronomical values:

```
usgs_id,usgs_mag,event_at,solaration_year,solar_secs,lunar_secs,midnight_secs,longitude
```

### Pagination Handling
- USGS API limits responses to 20,000 events
- For large date ranges, the collector will automatically paginate by splitting the time range if needed

---

## Dependencies

```
skyfield       # Astronomical calculations (ephemeris-based)
requests       # HTTP client for USGS API (or httpx)
```

Standard library only: `csv`, `datetime`, `argparse`

> **QUESTION 6:** Do you have a preferred package manager? The `.gitignore` covers pipenv, poetry, pdm, and uv. I'd suggest **uv** for simplicity unless you have a preference.

> **Answer 6:** I do not have a preference for package manager. Please use your suggestion.
