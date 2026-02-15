# Midnight and the `midnight_secs` Metric

## The Problem with Time Zones

When an earthquake occurs, the USGS records its timestamp in **UTC** (Coordinated Universal Time). But UTC tells us nothing about where the Sun was relative to the earthquake's location. Was it directly overhead? On the opposite side of the Earth? Somewhere in between?

Civil time zones might seem like the answer, but they are **geopolitical boundaries**, not physical ones. Time zones zigzag around national borders, observe daylight saving time at inconsistent dates, and can span up to 3 hours of actual solar difference within a single zone. For gravitational research, we need the **true local solar time** at the event's longitude.

## What Is `midnight_secs`?

`midnight_secs` is the **number of seconds elapsed since local solar midnight** at the earthquake's longitude. It represents the Sun's rotational position relative to the event location --- essentially, how far the Earth has rotated the event site past the point directly opposite the Sun.

```
midnight_secs = (utc_seconds_since_midnight + longitude_offset) mod 86,400
```

Where:
```
longitude_offset = longitude / 360 * 86,400 seconds
```

- **Minimum value**: 0 (event occurs exactly at local solar midnight)
- **Maximum value**: 86,399 (one second before the next local midnight)
- **Key value**: 43,200 (local solar noon --- Sun is closest to directly overhead)

### Why This Matters

The Sun's gravitational pull on a specific location changes as Earth rotates. At **local solar noon**, the Sun is at its closest angular approach to being directly overhead (modulated by declination/season). At **local solar midnight**, the Sun is on the opposite side of the Earth. `midnight_secs` directly encodes this rotational geometry.

## Four Worked Examples

All examples use a contrived location at **longitude -90** (90W, roughly the central United States --- near New Orleans or Memphis).

**Longitude offset calculation:**
```
offset = -90 / 360 * 86,400 = -21,600 seconds = -6 hours
```

This means local solar time at -90 longitude is always **6 hours behind UTC**.

---

### Example 1: Event at 00:00:00 UTC

```
UTC time:       00:00:00  (midnight UTC)
Local solar time: 00:00:00 - 6:00:00 = 18:00:00  (6:00 PM local)
midnight_secs:  64,800
```

**Calculation:**
```
utc_secs_since_midnight = 0
local_secs = (0 + (-21,600)) mod 86,400 = (-21,600) mod 86,400 = 64,800
```

<p align="center">

```
                        UTC midnight (00:00 UTC)
                              ↓
                         ·····+·····
                     ···       |      ···
                  ··           |          ··
                ·              |             ·
              ·                |               ·
             ·                 |                ·
            ·                  |                 ·
                               |
  Sunset ── ·     NIGHT SIDE   |   DAY SIDE     · ── Sunrise
            ·     (facing      |  (facing        ·
            ·      away)       |   the Sun)      ·
             ·                 |                ·
              ·                |               ·
                ·              |             ·     ☀ Sun direction
                  ··           |          ··       ──────────────→
                     ···       |      ···
                         ·····+·····

                     ▲
                     ╳  ← Location at -90° long.
                         Local time: 18:00 (evening)
                         midnight_secs = 64,800
                         Sun is SETTING (approaching horizon)
```

</p>

---

### Example 2: Event at 06:00:00 UTC

```
UTC time:       06:00:00  (6 AM UTC)
Local solar time: 06:00:00 - 6:00:00 = 00:00:00  (local solar midnight)
midnight_secs:  0
```

**Calculation:**
```
utc_secs_since_midnight = 21,600
local_secs = (21,600 + (-21,600)) mod 86,400 = 0 mod 86,400 = 0
```

<p align="center">

```
                          06:00 UTC
                              ↓
                         ·····+·····
                     ···       |      ···
                  ··           |          ··
                ·              |             ·
              ·                |               ·
             ·                 |                ·
            ·                  |                 ·
                               |
  Sunset ── ·     NIGHT SIDE   |   DAY SIDE     · ── Sunrise
            ·     (facing      |  (facing        ·
            ·      away)       |   the Sun)      ·
             ·                 |                ·
              ·                |               ·
                ·              |             ·     ☀ Sun direction
                  ··           |          ··       ──────────────→
                     ···       |      ···
                         ·····+·····
                               |
                               ╳  ← Location at -90° long.
                                    Local time: 00:00 (midnight)
                                    midnight_secs = 0
                                    Sun is DIRECTLY OPPOSITE (farthest away)
```

</p>

---

### Example 3: Event at 12:00:00 UTC

```
UTC time:       12:00:00  (noon UTC)
Local solar time: 12:00:00 - 6:00:00 = 06:00:00  (6:00 AM local)
midnight_secs:  21,600
```

**Calculation:**
```
utc_secs_since_midnight = 43,200
local_secs = (43,200 + (-21,600)) mod 86,400 = 21,600
```

<p align="center">

```
                          12:00 UTC
                              ↓
                         ·····+·····
                     ···       |      ···
                  ··           |          ··
                ·              |             ·
              ·                |               ·
             ·                 |                ·
            ·                  |                 ·
                               |
  Sunset ── ·     NIGHT SIDE   |   DAY SIDE     · ── Sunrise
            ·     (facing      |  (facing        ·
            ·      away)       |   the Sun)      ·
             ·                 |                ·
              ·                |               ·
                ·     ╳        |             ·     ☀ Sun direction
                  ·· ↑         |          ··       ──────────────→
                     ···       |      ···
                         ·····+·····

                     Location at -90° long.
                     Local time: 06:00 (morning)
                     midnight_secs = 21,600
                     Sun is RISING (crossing the horizon)
```

</p>

---

### Example 4: Event at 18:00:00 UTC

```
UTC time:       18:00:00  (6 PM UTC)
Local solar time: 18:00:00 - 6:00:00 = 12:00:00  (local solar noon)
midnight_secs:  43,200
```

**Calculation:**
```
utc_secs_since_midnight = 64,800
local_secs = (64,800 + (-21,600)) mod 86,400 = 43,200
```

<p align="center">

```
                          18:00 UTC
                              ↓
                         ·····+·····
                     ···       |      ···
                  ··           |          ··
                ·              |             ·
              ·                |               ·
             ·                 |                ·
            ·                  |                 ·
                               |
  Sunset ── ·     NIGHT SIDE   |   DAY SIDE     · ── Sunrise
            ·     (facing      |  (facing        ·
            ·      away)       |   the Sun)      ·
             ·                 |                ·
              ·                |               ·
                ·              |  ╳          ·     ☀ Sun direction
                  ··           |  ↑       ··       ──────────────→
                     ···       |      ···
                         ·····+·····

                     Location at -90° long.
                     Local time: 12:00 (solar noon)
                     midnight_secs = 43,200
                     Sun is CLOSEST (nearest to overhead)
```

</p>

---

## Summary of Examples

| UTC Time | Local Solar Time | midnight_secs | Sun Position Relative to Location |
|---|---|---|---|
| 00:00:00 | 18:00:00 (6 PM) | 64,800 | Setting --- approaching the far side |
| 06:00:00 | 00:00:00 (midnight) | 0 | Directly opposite --- farthest from location |
| 12:00:00 | 06:00:00 (6 AM) | 21,600 | Rising --- crossing the horizon |
| 18:00:00 | 12:00:00 (noon) | 43,200 | Overhead --- closest to location |

## The Full Daily Cycle

<p align="center">

```
Sun's Angular Proximity to Event Location vs. midnight_secs

  Closest    ·                         ╱╲
  (noon)     ·                        ╱  ╲
             ·                       ╱    ╲
             ·                      ╱      ╲
             ·                     ╱        ╲
             ·                    ╱          ╲
             ·                   ╱            ╲
             ·                  ╱              ╲
             ·                 ╱                ╲
             ·                ╱                  ╲
             ·               ╱                    ╲
             ·              ╱                      ╲
             ·             ╱                        ╲
             ·            ╱                          ╲
  Farthest   ·──+────────╱────────────────────────────╲────────+──
  (midnight) ·  |       ╱                              ╲       |
             0     21,600       43,200       64,800       86,400
                                                     midnight_secs
           Midnight  Sunrise      Noon       Sunset    Midnight
             (0h)     (6h)       (12h)       (18h)      (24h)
```

</p>

## Why Not Use Time Zones?

| Approach | Based on | Consistent? | Physically meaningful? |
|---|---|---|---|
| Civil time zone | Political boundaries | No (DST, zone width varies) | No |
| UTC offset (e.g. UTC-6) | Convention | Mostly (but zones are wide) | Approximate |
| `midnight_secs` | Exact longitude | Yes (pure math) | Yes --- directly encodes solar angle |

A location at -89 longitude and one at -91 longitude may share the same civil time zone, but their `midnight_secs` values will correctly reflect the ~480-second difference in solar position. This precision matters when looking for subtle gravitational correlations across thousands of events.

## How It Is Calculated in Code

The calculation is pure arithmetic --- no ephemeris lookup required:

```python
# Seconds since UTC midnight
utc_midnight = event_at.replace(hour=0, minute=0, second=0, microsecond=0)
utc_secs_since_midnight = (event_at - utc_midnight).total_seconds()

# Longitude offset: degrees → seconds (positive east, negative west)
offset_secs = int(longitude / (360.0 / 86400))

# Local solar time, wrapped to 0–86399
midnight_secs = int((utc_secs_since_midnight + offset_secs) % 86400)
```

The formula `longitude / 360 * 86,400` converts degrees of longitude into seconds of time. Earth rotates 360 degrees in 86,400 seconds (24 hours), so each degree of longitude equals exactly 240 seconds of solar time. For our -90 example: -90 * 240 = -21,600 seconds = -6 hours.
