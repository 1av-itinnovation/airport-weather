# 1AV Airport Weather Monitoring

A view-only dashboard that watches the weather at the 36 Philippine airports served by Cebu Pacific
and Cebgo, together with nearby earthquakes and typhoons. It shows which airports need attention,
why, and how reliable each reading is.

## Alert levels

| Level | Meaning | What staff do |
|---|---|---|
| Normal | No bad weather expected today | No action needed |
| Advisory | Bad weather expected later today | Plan ramp work around it |
| Warning | Bad weather within 1 hour, or already happening | As a precaution, be ready to pause ramp work. Stay alert and work carefully |
| Danger | A thunderstorm is at the airport now | Work at the ramp with extra care. Safety is the priority at all times |

## Features

**The screen**

- **One screen.** Map on the left, airport list in the middle, details on the right. On a phone
  these become three tabs.
- **Level tiles.** Show the count at each level and filter the map and list when tapped.
- **Today and Tomorrow.** Switches the list between today's alerts and tomorrow's forecast.
- **Region and Find an airport.** Narrow to Luzon, Visayas or Mindanao, or jump to one airport.
- **Map.** Airports as dots coloured by level; a flashing dot for a thunderstorm now; a dashed
  outline for an Estimate; purple rings for earthquakes. Zoom with the buttons, mouse wheel, pinch
  or double-tap.
- **Help.** The ? at the top explains everything in plain language and shows which source supplied
  the data at the latest check.

**An airport's details**

- **Right now** and **Rest of today**, with clock times.
- **Rain in the next 12 hours:** chance of rain, how heavy (Dry, Light, Moderate, Heavy) and the
  amount, hour by hour, with a lightning mark where the official forecast has a thunderstorm.
- **Tomorrow.**
- **Next 7 days:** chance of rain, a day and a night picture including thunderstorms, and the high
  and low temperature.
- **What to do**, **Confidence**, **Updated** and **Source**.

**Rain on the map**

- The map plays the forecast rain for the next 24 hours by itself, with Stop, Play and a slider.
- Lightning marks and dashed areas come only from official thunderstorm warnings and airport
  forecasts.
- A more detailed rain map from Windy.com can be opened from the details panel.

**Alerts and automatic behaviour**

- **Alert bar** for Danger airports, strong earthquakes and possible tsunami, with a warning sign in
  the browser tab and an optional soft two-note chime. Earthquake alerts show the time it happened
  and how long ago.
- **Nearest airport first.** On opening, the browser asks once for the viewer's location and shows
  the nearest airport. The location is used only in the browser and is not sent or stored.
- **Auto-show alerts.** With nobody using the screen, the map zooms to each earthquake alert, then
  each Danger airport, then returns to the whole map and repeats.
- **Early earthquake notice.** Between updates, an open page asks USGS once a minute and shows a
  qualifying earthquake at once, until the next update confirms it.
- **Next update time.** Worked out from the average gap between recent updates.
- **Yellow notice** when a backup source is in use or the data is more than 60 minutes old.

## How it works

1. **Collect.** On a schedule, reads the latest public data from the sources below. The
   schedule asks for every 10 minutes; in practice the hosting service runs it about every 20 to 25
   minutes.
2. **Choose the best source.** For each kind of data it uses the first-choice source. If that cannot
   be reached, it switches to a backup by itself.
3. **Apply the rules.** It works out each airport's alert level, the outlooks, the earthquake and
   tsunami alerts and the typhoon watch, and writes the result.
4. **Show.** The page reads that file and looks for newer data by itself: every
   5 minutes while an update is not due, every minute once it is. Viewers never need to reload.
5. **Flag problems.** A yellow notice appears when a backup is in use or the data is old.

The moving rain layer is built separately every 3 hours and saved.

## Where the data comes from

| Data | First choice | Backup |
|---|---|---|
| Airport reports and forecasts (issued by PAGASA) | aviationweather.gov | NOAA data server (same reports) |
| Estimates (airports with no official report) | MET Norway | Open-Meteo |
| Chance of rain and the 7-day outlook | Open-Meteo | none; the items are left out |
| Typhoon watch and thunderstorm area warnings | Aviation storm warnings (aviationweather.gov) | GDACS (position only) |
| Earthquakes | PHIVOLCS | USGS, then EMSC |
| Rain on the map | MET Norway forecast grid | none |
| Detailed rain map (optional) | Windy.com embedded map | none |

Accuracy ranking, highest first: official airport report, official airport forecast, official
aviation area warning, computer forecast estimate. When sources differ, the higher-ranked one is
used. Idle backups are tested every 6 hours and the result is shown in Help.

## The rules it follows

- **Danger** is given only when an official airport report says a thunderstorm is at the airport now.
  An Estimate can never be Danger.
- **Bad weather** in an official report or forecast means a thunderstorm, rain or rain showers, or
  strong winds.
- **"Possible at times"** means the official forecast says the weather may come and go during a
  period. "Expected" means the forecast is firm.
- **Bad weather in an Estimate** means 2.5 mm or more of rain in an hour, or winds of 39 km/h or more.
- **How heavy.** Light is under 2.5 mm of rain in an hour, Moderate is 2.5 mm or more, Heavy is
  7.6 mm or more.
- **Area warnings.** An airport inside an official thunderstorm or tropical cyclone area warning is
  raised to Warning.
- **Earthquakes shown** are magnitude 4.5 or stronger in the Philippine area over the past 7 days.
- **Earthquake alerts** cover the last 24 hours: magnitude 5.0 or stronger within 100 km of an
  airport, or magnitude 6.0 or stronger anywhere in the Philippine area.
- **Aftershocks** (below magnitude 5.0, within 100 km of a main earthquake of 5.0 or stronger, in
  the 72 hours after it) are grouped with the main earthquake: small dots on the map, one list in
  its details.
- **Two agencies.** For strong earthquakes the USGS figure is shown beside the PHIVOLCS figure, and
  the more cautious of the two positions decides whether an airport is within 100 km.
- **Possible tsunami** is shown for an earthquake of magnitude 6.5 or stronger no deeper than 70 km,
  or one that USGS has flagged for tsunami information. It is a prompt to check PHIVOLCS bulletins,
  not an official tsunami warning.

## What it cannot do

- It supports decisions. It does not replace official bulletins, official tsunami warnings, or the
  judgement of staff at the airport.
- It does not detect lightning.
- Estimates show rain and wind only and cannot confirm thunderstorms.
- Earthquakes cannot be predicted; only past ones are shown.
- Forecasts for tomorrow and the days ahead are less certain than today.
- Agencies report different magnitudes for the same earthquake, and first figures are often
  revised. The dashboard shows the PHIVOLCS figure and follows its revisions.
- No earthquake source is instant: agencies usually publish 5 to 20 minutes after the event.
- PAGASA's public typhoon bulletins are not published as data, so they are not read directly.
  Confirm typhoon decisions against PAGASA.

## Data credits

Weather and earthquake data belong to their publishers: PAGASA, the US Aviation Weather Center and
NOAA, the Norwegian Meteorological Institute (MET Norway), Open-Meteo, GDACS, PHIVOLCS, USGS and
EMSC. The optional detailed rain map is provided by Windy.com.

## Copyright

© 2026 1Aviation Groundhandling Services, Corp. All rights reserved.

Developed by the 1AV IT Department. Created under 1AV IT Innovation by Jake V Borras.
