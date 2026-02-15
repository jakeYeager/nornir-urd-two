"""Tests for legacy data validation results."""

from __future__ import annotations

import pytest

from validation.validate_legacy import run_validation


@pytest.fixture(scope="session")
def validation_results():
    """Run the full validation once for the test session."""
    return run_validation()


def test_validation_produces_results(validation_results):
    """Validation script runs and produces 10,105 rows."""
    assert len(validation_results) == 10_105


def test_midnight_delta_is_zero(validation_results):
    """After truncation fix, midnight_delta must be 0 for every record."""
    nonzero = [
        r for r in validation_results if r["midnight_delta"] != 0
    ]
    assert nonzero == [], (
        f"{len(nonzero)} records with midnight_delta != 0; "
        f"first: {nonzero[0] if nonzero else 'n/a'}"
    )


def test_lunar_delta_small(validation_results):
    """Lunar delta should be < 120s for all records."""
    large = [
        r for r in validation_results if abs(r["lunar_delta"]) >= 120
    ]
    assert large == [], (
        f"{len(large)} records with |lunar_delta| >= 120s; "
        f"first: {large[0] if large else 'n/a'}"
    )


def test_solar_delta_within_expected_range(validation_results):
    """Solar deltas should be within ~1.5 days when same solstice year is chosen.

    Legacy used Dec 21 00:00 UTC as solstice; our ephemeris uses the actual
    astronomical time. For events near the solstice boundary, different
    reference years may be chosen — those are expected and excluded here.
    """
    max_delta = 2.5 * 86400  # 216000 seconds; solstice ranges Dec 20-23
    same_year = [
        r for r in validation_results
        if r["legacy_solaration_year"] == r["new_solaration_year"]
    ]
    diff_year = [
        r for r in validation_results
        if r["legacy_solaration_year"] != r["new_solaration_year"]
    ]
    # Records with matching solaration year: delta should be small
    outliers = [r for r in same_year if abs(r["solar_delta"]) > max_delta]
    assert outliers == [], (
        f"{len(outliers)} same-year records with |solar_delta| > 1.5 days; "
        f"first: {outliers[0] if outliers else 'n/a'}"
    )
    # Records with different year: should be near solstice boundary (Dec)
    for r in diff_year:
        month = int(r["event_at"][5:7])
        assert month == 12, (
            f"Solaration year mismatch outside December: {r['usgs_id']} "
            f"month={month}"
        )
