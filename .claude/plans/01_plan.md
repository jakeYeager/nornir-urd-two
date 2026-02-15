I have a legacy Rails application for collecting, manipulating and storing information for a larger data analysis project related to earthquake events. I would like to build a series of Python scripts or small application solution to simplify and streamline this data collection process. Please output your implementation plan suggestions and questions in `review/01_plan_review.md` for me to review.

## Solution Requirements

### Phase 1 - astronomical calculations

This is where I think Python can be useful as a core requirement for data analysis is addition of astronomical calculations added to the USGS data. My research suggest that the Python library PyEphem can be used to make these calculations.

PyEphem must be able to provide:
- Solstice and equinox date/times UTC from 1948-12-21 to 2050-12-21
- New moon date/times UTC from 1948-12-21 to 2050-12-21
- CRITICAL: If this is not possible with PyEphem then another Python library will need to be used. If no library is available then stop further planning and research another solutions.

**Astronomical attributes**

Each USGS event record should have additional astronomical calculations added. These values relate to the geometrical positions of the sun and moon to the surface to the earth at the time of the event. These calculations are broken up in to three areas:

- Annual solar-earth orbital position. This is important to judge where the earth is in it's orbit to judge where to sun is in it declination.
- Monthly lunar-earth position. This is important to know where the moon is in it's orbit and it's position relative to the sun.
- Daily solar-earth rotational position relative to the earth's surface. This is important to know where the sun is relative to the event's location.

My legacy Rails application used the following concepts and conventions to create the calculations:

- *Solaration* - `solar_secs`: the period between consecutive winter solstice events (a.k.a hibernal solstice, or northern hemisphere solstice)
  - `solar_secs` is the elapsed time between the starting solstice and the event, before the ending solstice has occured
- *Lunation* - `lunar_secs`: the period between consecutive new moon phases. I believe this is typical to lunation in astronomy
  - `lunar_secs` is the elapsed time between the starting new moon and event, before the ending new moon has occured
- *Midnight* - `midnight_secs`: the local time based on longitude relative to UTC. It is critical to NOT use any locale or timezones as they are geopolitical boundaries and misleading. The Midnight convention is closer to a "elapsed radian" measurement translated into a time value

Pseudo-code of how `midnight_secs` was calculated on the legacy  ActiveRecord model:

```ruby
def midnight_secs = (time_at_longitude - time_at_longitude.at_midnight).to_i
def time_at_longitude = self.event_at + seconds_from_utc
def seconds_from_utc = (self.longitude / (360.0 / 24.hours)).to_i
```

### Phase 2 - legacy data validation and testing

I have existing data for us to test and validate against located at @data/legacy_data.csv. I know that there is the following issues with the data that need to be reviewed, tested and addressed:

- `solar_secs` is dirty as the Solarations where created without using specific astronomical event times. I used generic `YYYY/12/21T00:00:00Z` to approximate the winter solstice. Thus, these values will be off when compared with ephemeris data
- `lunar_secs` should be pretty close as I did attempt to use exact new moon event timestamps. However in my data analysis there appears to be slight deficits which could indicate calculation errors
- `midnight_secs` is suspect as it is a wholly contrived measuement that could contain defects. This is a critical measuement so proper review and testing is required


### Phase 3 - new data collction

- Data should be collected from the USGS API
  - Documentation for the USGS API is located here: https://earthquake.usgs.gov/fdsnws/event/1/
- Collected data should be stored in CSV format for review and post-processing
- The solution should:
  - be able to accept search query parameter inputs for max/min latitude, max/min longitude, max/min magnitude, max/min date range
  - have default search query parameters if none are supplied
- The critical attributes to save from the API response are the events:
  - USGS ID - `usgs_id`
  - Assigned USGS magnitude - `usgs_mag`
  - The timestamp of occurance - `event_at`
  - The event's location logitude - `longitude`
