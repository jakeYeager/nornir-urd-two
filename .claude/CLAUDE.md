# CLAUDE.md

## Project Description

Collect historical earthquake catalogs from the USGS ComCat API and enrich each event with astronomical metrics that encode the gravitational geometry of the Sun and Moon at the time and location of the event. The enriched catalogs support statistical analysis of whether celestial body positioning and tidal forcing correlate with seismic activity. This collection method is accessible via the CLI and includes a declustering utility that uses the Gardner-Knopoff (1974) algorithm.

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
│   ├── cli.py               (argparse CLI - collect + decluster commands)
│   ├── decluster.py         (Gardner-Knopoff 1974 declustering)
│   └── usgs.py              (USGS earthquake API client)
├── tests/
│   ├── test_astro.py        (astronomical calculation tests)
│   ├── test_cli.py          (CLI integration tests)
│   ├── test_decluster.py    (declustering algorithm tests)
│   └── test_usgs.py         (USGS client tests)
├── data/
│   └── output/              (collected data, gitignored CSVs)
├── review/
│   ├── 01_plan_review.md    (documentation of plan 01)
│   ├── 03_plan_review.md    (OpenQuake / declustering evaluation)
│   └── no_open_quake.md     (decision: why OpenQuake was not adopted)
├── metric_info_solar.md        (solar_secs metric explainer)
├── metric_info_lunar.md        (lunar_secs metric explainer)
├── metric_info_midnight.md     (midnight_secs metric explainer)
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
- Decluster: `uv run python -m nornir_urd decluster --input data/output/earthquakes.csv --mainshocks data/output/mainshocks.csv --aftershocks data/output/aftershocks.csv`

## Architecture Notes

- `astro.py` pre-computes solstice and new moon tables using Skyfield, then provides `solar_secs`, `lunar_secs`, and `midnight_secs` for event enrichment
- `usgs.py` fetches earthquake data from the USGS FDSN API; `eventtype=earthquake` is hardcoded
- `cli.py` orchestrates fetching + enrichment, outputting enriched CSV; also provides the `decluster` subcommand
- `decluster.py` implements Gardner-Knopoff (1974) declustering using pure-Python Haversine distance and the original empirical window formulas. OpenQuake Engine was evaluated and rejected due to dependency bloat (see `review/no_open_quake.md`)
- Output CSV columns: `usgs_id, usgs_mag, event_at, solaration_year, solar_secs, lunar_secs, midnight_secs, latitude, longitude, depth`
