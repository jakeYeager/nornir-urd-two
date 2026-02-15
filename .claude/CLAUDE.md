# CLAUDE.md

## Project Description

Nornir-urd-two: Verify and validate existing datasets as well as explore possible options to streamline new data collection. Includes astronomical calculation utilities (solstice/lunar timing) and a USGS earthquake data collection CLI.

## File Structure

```
nornir-urd-two/
├── .claude/
│   ├── CLAUDE.md           (this file)
│   └── plans/
│        └── 01_plan.md
├── nornir_urd/
│   ├── __init__.py          (public exports)
│   ├── __main__.py          (python -m entry point)
│   ├── astro.py             (solstice/lunar/midnight calculations)
│   ├── cli.py               (argparse CLI - collect command)
│   └── usgs.py              (USGS earthquake API client)
├── tests/
│   ├── test_astro.py        (astronomical calculation tests)
│   ├── test_cli.py          (CLI integration tests)
│   ├── test_usgs.py         (USGS client tests)
│   └── test_validation.py   (legacy data validation tests)
├── data/
│   ├── legacy_data.csv      (historical earthquake dataset)
│   └── output/              (collected data, gitignored CSVs)
├── review/
│   ├── 01_plan_review.md
│   └── legacy_data_report.md
├── README.md
└── pyproject.toml
```

## Tech Stack

- Python project (>=3.9)
- Dependencies: `skyfield` (ephemeris/astronomy), `httpx` (USGS API)
- Dev: `pytest`
- Package manager: `uv`
- .gitignore is configured for: pytest, mypy, ruff, tox/nox, Jupyter, and multiple package managers (pipenv, poetry, pdm, uv)

## Key Commands

- Install: `uv sync`
- Tests: `uv run pytest tests/ -v`
- Collect data: `uv run python -m nornir_urd collect --output data/output/earthquakes.csv`

## Architecture Notes

- `astro.py` pre-computes solstice and new moon tables using Skyfield, then provides `solar_secs`, `lunar_secs`, and `midnight_secs` for event enrichment
- `usgs.py` fetches earthquake data from the USGS FDSN API; `eventtype=earthquake` is hardcoded
- `cli.py` orchestrates fetching + enrichment, outputting CSV matching the legacy format
- Output CSV columns: `usgs_id, usgs_mag, event_at, solaration_year, solar_secs, lunar_secs, midnight_secs, longitude`
