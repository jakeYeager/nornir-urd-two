# G-K Window Size Determination

**Date:** 2026-02-23
**Context:** An external data analysis report flagged that the Gardner-Knopoff (1974)
declustering windows "may work however the determining spatial and temporal parameters
could be too large," citing M=6.0 windows of "approximately 211 km and 220 days."

---

## Key Finding: Our Implementation Is Correct

Our implementation uses the standard empirical formulas from Gardner & Knopoff (1974):

| Formula | Expression |
|---|---|
| Distance (all M) | `10^(0.1238 × M + 0.983)` km |
| Time (M < 6.5) | `10^(0.5409 × M − 0.547)` days |
| Time (M ≥ 6.5) | `10^(0.032 × M + 2.7389)` days |

**M=6.0 reference values:**

| Quantity | Our result | External report |
|---|---|---|
| Distance | **53 km** | 211 km |
| Time | **499 days** | 220 days |

Our values match the standard empirical fits reproduced in van Stiphout et al. (2012)
*"Seismicity declustering"* (Community Online Resource for Statistical Seismicity
Analysis) and the ZMAP toolbox reference implementation.

---

## Where the External Report's Values Come From

Working backwards from the external values reveals they do not correspond to any
reasonable earthquake magnitude under the G-K 1974 formulas:

**211 km distance:**
```
0.1238 × M + 0.983 = log10(211) = 2.324
M = (2.324 − 0.983) / 0.1238 ≈ 10.8   ← nonphysical
```

**220 days time (using M < 6.5 branch):**
```
0.5409 × M − 0.547 = log10(220) = 2.342
M = (2.342 + 0.547) / 0.5409 ≈ 5.3
```

These values cannot both refer to M=6.0 under the G-K formulas. The external analysis
either used a different parameterization of the window functions, applied them at a
different magnitude, or conflated values from different references. The discrepancy is
in the external report, not in our code.

---

## Why the Windows Feel Large for This Catalog

The G-K windows are large for M≥6.0 events by design:

| Magnitude | Distance window | Time window |
|---|---|---|
| M 6.0 | 53 km | 499 days (≈ 1.4 years) |
| M 6.5 | 61 km | 885 days (≈ 2.4 years) |
| M 7.0 | 71 km | 918 days (≈ 2.5 years) |
| M 8.0 | 88 km | 988 days (≈ 2.7 years) |

This is a known property of the algorithm, not a defect:

1. **Original calibration range.** G-K (1974) was fit to California seismicity in the
   M 3.0–6.5 range. The formulas are extrapolated when applied to M≥6.0 global events.

2. **Large events have long aftershock sequences.** A M=7.0 earthquake can produce
   aftershocks for years. The ~918-day window captures the bulk of that sequence.

3. **Global dense fault zones amplify dependent clustering.** A catalog spanning 70+
   years of global M≥6.0 seismicity includes tight spatial clusters around subduction
   zones (Japan, Indonesia, Aleutians). Large time windows naturally classify many
   events in these zones as dependent.

The resulting classification rates (≈ 37% of the 9,802-event catalog flagged as
aftershocks/foreshocks) are consistent with published G-K applications to global
high-magnitude catalogs.

---

## Conclusion

The implementation is correct. The large window sizes and the ~37% dependent-event
rate are inherent properties of applying the Gardner-Knopoff (1974) algorithm to a
global M≥6.0 catalog — not a bug.

If tighter independence criteria are required for a specific analysis, alternative
algorithms designed for global high-magnitude catalogs (ETAS, Reasenberg) are worth
evaluating in future work.
