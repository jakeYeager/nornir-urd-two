# Plan 05 — `window` Subcommand

Source requirements: `review/05_window_req.md`

---

## Summary

Add a `window` subcommand that runs the Gardner-Knopoff declustering algorithm with a user-supplied scalar multiplier applied to both window dimensions (distance and time). The aftershock output gets four additional attribution columns: `parent_id`, `parent_magnitude`, `delta_t_sec`, `delta_dist_km`. Overlapping-window ties are broken by temporal proximity (smallest `|delta_t_sec|` wins).

---

## Implementation Questions

The following need answers before coding begins:

**Q1 — Window-size multiplier scope**
Does `--window-size` scale both the spatial (km) and temporal (days) windows by the same factor, or are they scaled independently? The requirement says "alter the G-K algorithm window parameters by percentage" without distinguishing the two dimensions. Assuming proportional scaling of both: `dist *= scale`, `time *= scale`.

**Answer 1:** Scale both.

**Q2 — `delta_t_sec` sign convention**
The G-K algorithm flags both foreshocks (events *before* the mainshock) and aftershocks (events *after*). Should `delta_t_sec` be signed — negative when the dependent event precedes the mainshock — or always a positive absolute value? A signed value encodes directionality and may be useful downstream; unsigned is simpler and matches the column name "elapsed seconds."

**Answer 2:** Signed.

**Q3 — "More recent mainshock" definition**
The overlap rule says "assign `parent_id` to the **more recent mainshock**" with the parenthetical "(temporal proximity takes priority over spatial proximity)". Two possible readings:
- **Smallest `|delta_t_sec|`** — the mainshock *closest in time* to the dependent event (could be earlier or later)
- **Latest `event_at` timestamp** — the mainshock that occurred *most recently in calendar time*

The parenthetical suggests "closest in time", but the phrasing "more recent" suggests "latest timestamp". Which is intended?

**Answer 3:** Smallest `delta_t`.

**Q4 — `--window-size` required or optional with default**
Should `--window-size` be a required argument, or default to `1.0` (standard G-K, equivalent to `decluster`)? If it defaults to 1.0 the subcommand becomes a superset of `decluster`. If required, callers always opt in to a specific parameterization.

**Answer 4:** `--window-size` should be required, and `window` should be the only subcommand that returns the new, additional columns to *aftershock* output.

**Q5 — Mainshock output columns**
The requirement says the *aftershock* output gets additional columns. Should the mainshock output be identical to what `decluster` produces (original columns only), or should it also carry any attribution metadata?

**Answer 5:** No changes to the *mainshock* output and should remain identical to the previous implementation.

---

## Architecture

### New / modified files

| File | Change |
|---|---|
| `nornir_urd/decluster.py` | Add `gk_window_scaled(magnitude, scale)` and `decluster_with_parents(events, window_scale)` |
| `nornir_urd/cli.py` | Add `window` subparser and `_run_window()` handler |
| `tests/test_window.py` | New test module for scaled windows, parent attribution, overlap resolution |

No new top-level modules are needed; the window logic is a thin extension of the existing declustering code.

### `decluster.py` additions

```python
def gk_window_scaled(magnitude: float, scale: float) -> tuple[float, float]:
    """G-K (1974) windows multiplied by `scale`."""
    dist_km, time_days = gk_window(magnitude)
    return dist_km * scale, time_days * scale


def decluster_with_parents(
    events: list[dict],
    window_scale: float = 1.0,
) -> tuple[list[dict], list[dict]]:
    """G-K declustering with per-aftershock parent attribution.

    Returns:
        (mainshocks, aftershocks)
        Each aftershock dict gains: parent_id, parent_magnitude,
        delta_t_sec, delta_dist_km.

    Overlap rule: when multiple mainshocks claim the same event,
    the one with the smallest |delta_t_sec| is assigned as parent.
    """
```

**Algorithm sketch:**
1. Process events magnitude-descending (same as current).
2. `is_dependent[j]` + `parent_idx[j]` arrays track classification and best-candidate parent.
3. For each mainshock `idx`, iterate candidate dependents. If `j` is already claimed, compare `|delta_t|` against the existing parent; re-assign if the new mainshock is closer in time.
4. After the loop, build output dicts for aftershocks with the four extra columns computed from the assigned parent.

This changes the O(n²) inner loop slightly: instead of skipping already-dependent events early (current line: `if is_dependent[j]: continue`), we must still evaluate them to check for a closer parent. The `is_dependent[j]` guard that prevents *re-classifying as mainshock* remains; only the parent assignment is updatable.

### `cli.py` additions

```python
window_p = sub.add_parser(
    "window",
    help="Decluster with a scaled G-K window and produce aftershock attribution columns",
)
window_p.add_argument("--window-size", type=float, required=True,
                      help="Scalar multiplier for G-K windows (e.g. 0.75 or 1.25)")
window_p.add_argument("--input", required=True)
window_p.add_argument("--mainshocks", required=True)
window_p.add_argument("--aftershocks", required=True)
```

`_run_window()` mirrors `_run_decluster()`, replacing the call to `decluster_gardner_knopoff` with `decluster_with_parents(events, window_scale=args.window_size)` and writing the extended aftershock fieldnames.

---

## Tests (`tests/test_window.py`)

| Test | Scenario |
|---|---|
| `test_scaled_window_smaller` | `gk_window_scaled(6.0, 0.75)` returns values 75% of standard |
| `test_scaled_window_larger` | `gk_window_scaled(6.0, 1.25)` returns values 125% of standard |
| `test_scale_1_matches_standard` | `window_scale=1.0` produces same classification as `decluster_gardner_knopoff` |
| `test_parent_columns_present` | Aftershock dicts contain all four extra keys |
| `test_parent_id_correct` | Single-mainshock case: `parent_id` matches mainshock's `usgs_id` |
| `test_delta_t_sec_value` | Known time offset produces correct `delta_t_sec` |
| `test_delta_dist_km_value` | Known coordinates produce correct `delta_dist_km` |
| `test_overlap_more_recent_wins` | Two mainshocks both covering same event → parent is the one closer in time |
| `test_tight_window_fewer_aftershocks` | `0.75` scale flags fewer events than `1.0` on same catalog |
| `test_wide_window_more_aftershocks` | `1.25` scale flags more events than `1.0` on same catalog |
| `test_mainshocks_no_extra_columns` | Mainshock rows do not contain `parent_id` etc. |
| `test_empty_catalog` | No crash on empty input |

---

## Open implementation detail

The current `decluster_gardner_knopoff` skips already-dependent events in the inner loop (`if is_dependent[j]: continue`). `decluster_with_parents` must remove that early-exit for dependent events so overlap resolution can re-evaluate their parent. The `is_dependent` flag itself still prevents a dependent event from being treated as a mainshock.
