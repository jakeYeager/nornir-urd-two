The requirements come from an external data analysis project that need a data product similar to the declustered CSVs produced by the `decluster` subcommand.  


## Implementation

The new subcommand should follow a similar pattern as the others in this project, with addition of `window-size` argument which would alter the G-K algorithm window parameters by percentage

Example CLI subcommand usage pattern:
```bash
uv run python -m nornir_urd window \
  --window-size 0.75 \
  --input data/output/global_events.csv \
  --mainshocks data/output/mainshocks.csv \
  --aftershocks data/output/aftershocks.csv
```

The originating CSV would then be split via the declustering algorithm similar to the existing `decluster` subcommand. The `aftershocks.csv` product will have additional columns added to support downstream data analysis.

Create an implementation plan that provides this functionality, provides tests, and satisfies the following the external data treatment requirements:

## External Data Treatment Requirements

**Part B — Algorithm Sensitivity:** Apply at least two alternative declustering parameterizations to the same source catalog to test whether the solar signal suppression is G-K-specific:

- G-K ×0.75 — tighter windows, fewer events removed
- G-K ×1.25 — wider windows, more events removed


The following columns should be added to the aftershock output:

| Column             | Content                                                     |
| ------------------ | ----------------------------------------------------------- |
| `parent_id`        | USGS ID of the triggering mainshock                         |
| `parent_magnitude` | Magnitude of the triggering mainshock                       |
| `delta_t_sec`      | Elapsed seconds between aftershock and its parent mainshock |
| `delta_dist_km`    | Distance in km between aftershock and its parent mainshock  |

**Edge case — overlapping G-K windows:** When two mainshock windows overlap in time and space and both could claim the same event, the algorithm shall assign `parent_id` to the **more recent mainshock** (temporal proximity takes priority over spatial proximity).
