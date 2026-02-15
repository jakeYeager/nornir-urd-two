# Plan 02

We have successfully created and tested the essential requirements! The next phase is documentation and explaination. The greater relevancy of the `solar_secs`, `lunar_secs` and `midnight_secs` metrics is their use in describing the gravitational force of celestial bodies effecting the occurance of seismic activity. It is a slight but statistically observable force. These metrics are used in concert to show celestial body positions in the data analysis

The problem is that this topic is fairly niche in the academic community, not well known to the general public, and these metrics are all "custom design". I need you to create an explanitory document to describe these metrics in language suitable for general public readability. 

Use any descriptive context in @.claude/plans/01_plan.md "Phase 1" as well as any calculation code we have (that is now tested and approved).

## Phase 1

**Solaration**

Customized concept of a annual calendar starting and ending according to the winter solstice. This should describe the changing position of the sun's maximum gravitational force through change in declination. `solar_secs` can be used as a metric to better track where the earth is in it's annual orbit, as opposed to the conventional calendaring system.

Please make supporting graphics how `solar_secs` signifies the change in solar declination through the course of a year.

Please create a document for me to review for this phase at review/info_solar_review.md.

## Phase 2

**Lunation**

Lunation is not as conceptually unknown but should be described as well along with how `lunar_secs` is calculated. It is important to describe and illustrate that `lunar_secs` metric is a reference not only to the lunar position but also the relationship between the sun and the moon's gravity acting in concert or opposition on the surface of the earth.

Please make supporting graphics to show how `lunar_secs` can signify both lunar position and lunar phase.

Please create a document for me to review for this phase at review/info_lunar_review.md.

**Midnight**

The concept of `midnight_secs` is the most unique. It is critial as this metric describes where the sun is in relation to the earth's surface at the moment of the earthquake occurance. Please create 4 examples for a contrived location at -90 longitude and show the translated time between UTC (earthquake time) and the longitude metric (true local time). Please use 00:00:00 UTC, 06:00:00 UTC, 12:00:00 UTC and 18:00:00 UTC for the examples.

Please make supporting graphics to illustrate the position of the sun in reference to the contrived location at each of the example times.

Please create a document for me to review for this phase at review/info_midnight_review.md.