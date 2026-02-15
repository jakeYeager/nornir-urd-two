# nornir-urd-two

Verify and validate existing datasets. Generate new sample populations of historical data.

## Installation

Requires [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

### Ephemeris data

The astronomical calculations depend on the JPL DE421 ephemeris (`de421.bsp`, ~17 MB). Skyfield downloads this file automatically on first run into the working directory. It is excluded from version control via `.gitignore`.

To download it manually:

```bash
uv run python -c "from skyfield.api import load; load('de421.bsp')"
```

## Tests

```bash
uv run pytest tests/ -v
```
