# Plan: Sequence Paradigm — Aftershock Attribution + Mainshock Summaries

## Context

Users running declustering commands need to understand the full sequence structure of each cluster: which event is the parent, what the temporal/spatial relationship is, and how large the sequence footprint is. Currently only the `window` subcommand provides parent attribution on aftershocks. This change extends that capability uniformly to `decluster`, `decluster-reasenberg`, and `decluster-a1b`, and adds four new summary columns to every mainshock output so analysts can filter and compare sequences across algorithms.

`decluster-table` is excluded (flagged for future removal).

---

## Files to Modify

- `nornir_urd/decluster.py`
- `nornir_urd/reasenberg.py`
- `nornir_urd/cli.py`
- `README.md`
- `tests/test_decluster.py`

---

## Step 1 — `decluster.py`: generalize `decluster_with_parents`

Extract the parent-tracking scan into a private `_gk_decluster_with_parents_core(events, window_fn)` that accepts any `window_fn(magnitude) -> (dist_km, time_days)`. Then update/add the public wrappers:

```
# existing — update to delegate
decluster_with_parents(events, window_scale=1.0)
    → _gk_decluster_with_parents_core(events, lambda m: gk_window_scaled(m, window_scale))

# new
decluster_gardner_knopoff_with_parents(events)
    → _gk_decluster_with_parents_core(events, gk_window)

decluster_a1b_with_parents(events, radius_km=83.2, window_days=95.6)
    → _gk_decluster_with_parents_core(events, lambda _: (radius_km, window_days))
```

No change to `_gk_decluster_core` or `decluster_gardner_knopoff_table` (used by `decluster-table`).

---

## Step 2 — `reasenberg.py`: add parent attribution to aftershock dicts

After cluster classification (where `main_si` is already tracked per cluster), iterate over aftershocks and enrich each dict with:

| Key | Value |
|---|---|
| `parent_id` | `sorted_evts[main_si]["usgs_id"]` |
| `parent_magnitude` | `sorted_evts[main_si]["usgs_mag"]` |
| `delta_t_sec` | `(times[i] - times[main_si]).total_seconds()` (signed; negative for foreshocks) |
| `delta_dist_km` | `haversine_km(...)` between aftershock and cluster mainshock |

No tie-breaking is needed for Reasenberg — each event belongs to exactly one cluster.

---

## Step 3 — `cli.py`: unified post-processing + updated runners

### 3a. Constants

```python
DECLUSTER_REQUIRED_COLUMNS = {"usgs_id", "event_at", "latitude", "longitude", "usgs_mag"}
# (adds usgs_id — applies to all decluster commands including decluster-table via _load_decluster_csv)

AFTERSHOCK_EXTRA_COLUMNS = ["parent_id", "parent_magnitude", "delta_t_sec", "delta_dist_km"]
MAINSHOCK_EXTRA_COLUMNS  = ["foreshock_count", "aftershock_count", "window_secs", "window_km"]
```

### 3b. New helper — `_attach_mainshock_summaries(mainshocks, aftershocks)`

Groups aftershocks by `parent_id`. For each mainshock, attaches:

| Column | Formula |
|---|---|
| `foreshock_count` | `sum(1 for a in group if float(a["delta_t_sec"]) < 0)` |
| `aftershock_count` | `sum(1 for a in group if float(a["delta_t_sec"]) >= 0)` |
| `window_secs` | `max(abs(float(a["delta_t_sec"])) for a in group)`, else `0` |
| `window_km` | `max(float(a["delta_dist_km"]) for a in group)`, else `0` |

Returns a new list of mainshock dicts with these four keys appended.

`window_secs` / `window_km` are the **observed maximum** across all claimed events (foreshocks and aftershocks). For G-K algorithms this equals the algorithm's theoretical window for that mainshock's magnitude. For Reasenberg (variable τ / r_int) this reports the actual reach observed in the data, which is the most meaningful and consistent metric. **This behavior is documented in README.md.**

### 3c. New write helper — `_write_decluster_outputs`

Replaces per-runner inline write logic for the four updated commands:

```python
def _write_decluster_outputs(args, fieldnames, mainshocks, aftershocks):
    ms_fieldnames = fieldnames + MAINSHOCK_EXTRA_COLUMNS
    as_fieldnames = fieldnames + AFTERSHOCK_EXTRA_COLUMNS
    mainshocks_out = _attach_mainshock_summaries(mainshocks, aftershocks)
    # write mainshocks_out with ms_fieldnames
    # write aftershocks with as_fieldnames
```

### 3d. Updated runners

| Runner | Change |
|---|---|
| `_run_decluster` | Call `decluster_gardner_knopoff_with_parents`; use `_write_decluster_outputs` |
| `_run_decluster_reasenberg` | Call `decluster_reasenberg` (now returns attributed aftershocks); use `_write_decluster_outputs` |
| `_run_decluster_a1b` | Call `decluster_a1b_with_parents`; use `_write_decluster_outputs` |
| `_run_window` | Compute `_attach_mainshock_summaries`; write mainshocks with `ms_fieldnames`, aftershocks unchanged |
| `_run_decluster_table` | **No change** — still uses `_write_mainshocks_aftershocks` with original fieldnames |

### 3e. Updated imports

Add `decluster_gardner_knopoff_with_parents`, `decluster_a1b_with_parents` to the import from `.decluster`.

---

## Step 4 — `README.md` updates

1. **"Declustering existing CSVs"** required columns table: add `usgs_id` row (mark as new requirement).
2. **For each affected subcommand** (`decluster`, `decluster-reasenberg`, `decluster-a1b`, `window`): add aftershock output columns table and mainshock output columns table (mirroring existing `window` docs).
3. **`window_secs` / `window_km` behavior note** (apply to all affected subcommands):
   > `window_secs` and `window_km` reflect the observed maximum `|delta_t_sec|` and `delta_dist_km` across all events (foreshocks and aftershocks) claimed by that mainshock. For G-K-based algorithms this equals the algorithm's theoretical window at the mainshock's magnitude. For Reasenberg, where the interaction radius and lookback window vary dynamically, these columns report the actual spatial and temporal reach observed in the data.
4. Update `window` docs: note that mainshock output now includes the four summary columns (previously it produced original columns only).

---

## Step 5 — Tests

In `tests/test_decluster.py`:

- Add `TestDeclustersWithParents` class covering `decluster_gardner_knopoff_with_parents` and `decluster_a1b_with_parents`:
  - Basic attribution keys present on aftershock dicts (`parent_id`, `parent_magnitude`, `delta_t_sec`, `delta_dist_km`)
  - `delta_t_sec` is negative for a foreshock (event before mainshock)
  - `delta_t_sec` is positive for a true aftershock
  - `delta_dist_km` matches expected haversine distance
  - Mainshocks carry no extra keys (clean pass-through)
  - Empty catalog returns `([], [])`

No test changes needed for `_gk_decluster_core` or `decluster_gardner_knopoff_table` (untouched).

---

## Verification

```bash
# Run all tests
uv run pytest tests/ -v

# Smoke test decluster
uv run python -m nornir_urd decluster \
  --input data/output/global_events.csv \
  --mainshocks /tmp/ms.csv \
  --aftershocks /tmp/as.csv

# Confirm aftershock columns present
head -1 /tmp/as.csv   # should include parent_id, parent_magnitude, delta_t_sec, delta_dist_km

# Confirm mainshock columns present
head -1 /tmp/ms.csv   # should include foreshock_count, aftershock_count, window_secs, window_km

# Repeat for decluster-reasenberg, decluster-a1b, window
```
