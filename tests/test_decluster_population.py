"""Population validation test for the Gardner-Knopoff declustering implementation.

Requires data/output/global_events_pre-review.csv (gitignored).
Skipped automatically when the file is absent.

Run with:
    uv run pytest tests/test_decluster_population.py -v -m slow
"""

import csv
import os

import pytest

from nornir_urd.decluster import decluster_gardner_knopoff

CSV_PATH = "data/output/global_events_pre-review.csv"

pytestmark = pytest.mark.skipif(
    not os.path.exists(CSV_PATH),
    reason="pre-review CSV not present",
)


class TestPopulationValidation:
    @pytest.mark.slow
    def test_decluster_real_catalog(self):
        """Declustering a 9,802-event global M≥6.0 catalog yields known-good counts.

        Expected split: 6,222 mainshocks + 3,580 aftershocks = 9,802 total.
        Runtime: 30–90 seconds (O(n²) with early-exit time pruning).
        """
        with open(CSV_PATH, newline="") as f:
            rows = list(csv.DictReader(f))

        events = [
            {
                "usgs_id": r["usgs_id"],
                "usgs_mag": float(r["usgs_mag"]),
                "event_at": r["event_at"],
                "latitude": float(r["latitude"]),
                "longitude": float(r["longitude"]),
            }
            for r in rows
        ]

        assert len(events) == 9802, f"Expected 9802 events, got {len(events)}"

        mainshocks, aftershocks = decluster_gardner_knopoff(events)

        assert len(mainshocks) + len(aftershocks) == 9802
        assert len(mainshocks) == 6222, (
            f"Expected 6222 mainshocks, got {len(mainshocks)}"
        )
        assert len(aftershocks) == 3580, (
            f"Expected 3580 aftershocks, got {len(aftershocks)}"
        )
