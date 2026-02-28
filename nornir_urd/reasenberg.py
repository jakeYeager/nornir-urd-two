"""Reasenberg (1985) earthquake cluster analysis.

Implements the interaction-based clustering algorithm from:
    Reasenberg P.A. (1985). Second-order moment of central California
    seismicity, 1969–1982. J. Geophys. Res., 90(B7), 5479–5495.
    https://doi.org/10.1029/JB090iB07p05479

Algorithm summary
-----------------
Events are processed in chronological order. Each unassigned event either
joins the nearest eligible open cluster or starts a new single-event cluster.
A cluster is "open" if the time since its last member event is less than the
cluster's adaptive lookback window τ. After all events are processed, within
each multi-event cluster the highest-magnitude event is the mainshock and all
others are aftershocks. Isolated single-event clusters are mainshocks.

Interaction radius
------------------
    r_int = rfact × 10^(0.11 × M + 0.024)  [km]

where M is the current maximum magnitude in the cluster and rfact scales the
zone (published default: 10).

Adaptive lookback window
------------------------
    τ = clamp( −ln(1 − p) / 10^(b × (M_max − xmeff)),  τ_min, τ_max )

For the ISC-GEM catalog (M ≥ 6.0) the denominator 10^(b×(M−xmeff)) is very
large, so τ typically collapses to τ_min = 1 day. τ_max = 10 days bounds
low-activity clusters.
"""

from __future__ import annotations

import math

from .decluster import _parse_event_time, haversine_km


def _r_int(mmax: float, rfact: float) -> float:
    """Interaction radius (km) for a cluster with maximum magnitude *mmax*."""
    return rfact * 10 ** (0.11 * mmax + 0.024)


def _tau(
    mmax: float,
    xmeff: float,
    p: float,
    tau_min: float,
    tau_max: float,
    b: float = 1.0,
) -> float:
    """Adaptive lookback window (days) for a cluster of maximum magnitude *mmax*.

    Returns τ clamped to [tau_min, tau_max].
    """
    exponent = b * (mmax - xmeff)
    # Guard against overflow for very large exponents (high-M clusters).
    if exponent > 300:
        return tau_min
    lam = 10.0 ** exponent
    tau = -math.log(1.0 - p) / lam
    return max(tau_min, min(tau_max, tau))


def decluster_reasenberg(
    events: list[dict],
    rfact: float = 10.0,
    tau_min: float = 1.0,
    tau_max: float = 10.0,
    p: float = 0.95,
    xmeff: float = 1.5,
) -> tuple[list[dict], list[dict]]:
    """Decluster a catalog using the Reasenberg (1985) algorithm.

    Each event dict must contain at minimum:
        event_at  -- ISO 8601 timestamp (str)
        latitude  -- float
        longitude -- float
        usgs_mag  -- float

    Any additional keys are preserved in the output.

    Args:
        events:   List of event dicts.
        rfact:    Interaction radius scale factor (default: 10).
        tau_min:  Minimum lookback window in days (default: 1.0).
        tau_max:  Maximum lookback window in days (default: 10.0).
        p:        Omori decay probability threshold (default: 0.95).
        xmeff:    Effective magnitude threshold (default: 1.5).

    Returns:
        (mainshocks, aftershocks) -- two lists of event dicts.
    """
    if not events:
        return [], []

    # Sort events chronologically (stable sort preserves original order for ties).
    order = sorted(range(len(events)), key=lambda i: events[i]["event_at"])
    sorted_evts = [events[i] for i in order]
    times = [_parse_event_time(e["event_at"]) for e in sorted_evts]
    n = len(sorted_evts)

    # Each cluster is a mutable list:
    #   [mmax, main_si, last_si, member_set]
    # where *_si indices reference sorted_evts.
    clusters: list[list] = []

    for i in range(n):
        t_i = times[i]
        m_i = float(sorted_evts[i]["usgs_mag"])
        lat_i = float(sorted_evts[i]["latitude"])
        lon_i = float(sorted_evts[i]["longitude"])

        best_ci = None
        best_dt = float("inf")

        for ci, (mmax_c, main_si, last_si, _members) in enumerate(clusters):
            dt_days = (t_i - times[last_si]).total_seconds() / 86400.0
            if dt_days > _tau(mmax_c, xmeff, p, tau_min, tau_max):
                continue  # cluster is closed
            dist = haversine_km(
                lat_i, lon_i,
                float(sorted_evts[main_si]["latitude"]),
                float(sorted_evts[main_si]["longitude"]),
            )
            if dist > _r_int(mmax_c, rfact):
                continue
            if dt_days < best_dt:
                best_dt = dt_days
                best_ci = ci

        if best_ci is not None:
            c = clusters[best_ci]
            c[3].add(i)
            if m_i > c[0]:      # new magnitude maximum — update mainshock
                c[0] = m_i
                c[1] = i
            c[2] = i            # update last-event pointer
        else:
            clusters.append([m_i, i, i, {i}])

    # Classify: within each multi-event cluster the highest-magnitude event
    # is the mainshock; all others are aftershocks/foreshocks.
    is_dependent = [False] * n
    for _mmax, main_si, _last_si, members in clusters:
        if len(members) == 1:
            continue
        for si in members:
            if si != main_si:
                is_dependent[si] = True

    mainshocks = [sorted_evts[i] for i in range(n) if not is_dependent[i]]
    aftershocks = [sorted_evts[i] for i in range(n) if is_dependent[i]]
    return mainshocks, aftershocks
