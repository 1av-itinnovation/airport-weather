# 1AV Airport Weather Monitoring

A view-only dashboard that watches the weather at the 36 Philippine airports served by Cebu Pacific
and Cebgo, together with nearby earthquakes and typhoons. It shows which airports need attention,
why, and how reliable each reading is.

Created under 1AV IT Innovation by Jake V Borras.

## How to read the dashboard

| Level | Meaning | What to do |
|---|---|---|
| Normal | No bad weather expected today | No action needed |
| Advisory | Bad weather expected later today | Plan ramp work around it |
| Warning | Bad weather within 1 hour, or already happening | Prepare to pause ramp work |
| Danger | A thunderstorm is at the airport now | Stop outdoor ramp work |

- **Map.** Each dot is an airport, coloured by its level. A flashing dot means a thunderstorm there
  now. A dashed outline means the reading is an Estimate. Purple rings are earthquakes.
- **Details.** Select an airport or earthquake to see its full report: right now, rest of today,
  tomorrow, days ahead, what to do, confidence, update time and source.
- **Rain layer.** The map plays the forecast rain for the next 24 hours by itself, with lightning
  marks where an official thunderstorm warning or airport forecast applies.
- **One screen.** Everything fits on a single screen: map on the left, airport list in the middle,
  details on the right. On a phone these become three tabs.
- **Filters.** The coloured boxes at the top filter the map and list by level and show the count at
  each level. Today and Tomorrow switch the list between today's alerts and tomorrow's forecast.
  Region narrows everything to Luzon, Visayas or Mindanao.
- **Earthquakes and Typhoon.** Tabs in the right-hand panel.
- **Help.** The ? at the top of the page explains everything in plain language and shows which
  source supplied the data at the latest check.

## How it works

1. **Collect.** Every 10 minutes `build.py` reads the latest public data from the sources below.
2. **Choose the best source.** For each kind of data it uses the first-choice source. If that cannot
   be reached, it switches to a backup by itself.
3. **Apply the rules.** It works out each airport's alert level, tomorrow's outlook, the earthquake
   flag and the typhoon watch, and writes the result to `docs/data.json`.
4. **Show.** The page (`docs/index.html`) reads that file and checks for newer data every 5 minutes.
   Viewers never need to reload.
5. **Flag problems.** If a backup source is in use, or the data is more than 60 minutes old, the
   page shows a yellow notice.

The moving rain layer is built separately every 3 hours and saved to `docs/rain.json`.

## Where the data comes from

| Data | First choice | Backup |
|---|---|---|
| Airport reports and forecasts | aviationweather.gov | NOAA data server (same official reports) |
| Estimates (airports with no official report) | MET Norway | Open-Meteo |
| Typhoon watch | Aviation storm warnings (aviationweather.gov) | GDACS (position only) |
| Earthquakes | PHIVOLCS | USGS, then EMSC |
| Rain layer | MET Norway forecast grid | none |
| Detailed rain map (optional) | Windy.com embedded map | none |

Accuracy ranking, highest first: official airport report, official airport forecast, official
aviation area warning, computer forecast estimate. When sources differ, the higher-ranked one is used.

## The rules it follows

- **Danger** is given only when an official airport report says a thunderstorm is at the airport now.
  An Estimate can never be Danger.
- **Bad weather** in an official report or forecast means a thunderstorm, rain or rain showers, or
  strong winds.
- **Bad weather in an Estimate** means 2.5 mm or more of rain in an hour, or winds of 39 km/h or more.
- **Area warnings.** An airport inside an official thunderstorm or tropical cyclone area warning is
  raised to Warning.
- **Earthquakes shown** are magnitude 4.5 or stronger in the Philippine area over the past 7 days.
- **Earthquake flag.** An airport is flagged when a magnitude 5.0 or stronger earthquake happened
  within 100 km of it in the last 24 hours.

## What it cannot do

- It supports decisions. It does not replace official bulletins or the judgement of staff at the
  airport.
- Estimates show rain and wind only and cannot confirm thunderstorms.
- It does not detect lightning.
- Earthquakes cannot be predicted; only past ones are shown.
- Forecasts for tomorrow and the days ahead are less certain than today.
- Agencies can report slightly different magnitudes for the same earthquake. The rules are applied
  to whichever source is in use.
- PAGASA is the official typhoon authority for the Philippines but publishes no data feed, so it is
  not read directly. Confirm typhoon decisions against PAGASA bulletins.

## Files

| File | Purpose |
|---|---|
| `build.py` | Collects the data, chooses sources, applies the rules. |
| `docs/index.html` | The dashboard page. |
| `docs/data.json` | Latest alert data, rewritten at every check. |
| `docs/rain.json` | Rain forecast grid for the moving rain layer. |
| `docs/assets/` | Map image and 1AV logo. |
| `.github/workflows/refresh.yml` | The 10-minute schedule. |

## Data credits

Weather and earthquake data belong to their publishers: the US Aviation Weather Center and NOAA,
the Norwegian Meteorological Institute (MET Norway), Open-Meteo, GDACS, PHIVOLCS, USGS and EMSC.
The optional detailed rain map is provided by Windy.com.

## Copyright

© 2026 1Aviation Groundhandling Services, Corp. All rights reserved.

Created under 1AV IT Innovation by Jake V Borras.

The dashboard design, code and alert rules may not be copied or reused without permission. The 1AV
name and logo are the property of 1Aviation Groundhandling Services, Corp.
