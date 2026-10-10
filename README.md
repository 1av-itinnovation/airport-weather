# 1AV Airport Weather Monitoring

A view-only dashboard that watches the weather at the 36 Philippine airports served by Cebu Pacific
and Cebgo, together with nearby earthquakes, volcanoes and typhoons. It shows which airports need attention,
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

- **Alerts as notifications.** Danger airports, strong earthquakes, possible tsunami, volcano alerts
  and typhoon alerts pop in under the title bar as slim coloured chips when the page opens and
  whenever a new alert arrives. After about 9 seconds they tuck away into the alert button in the
  title bar (a warning triangle with a red count), so nothing covers the map. Pressing the button
  brings them back; pressing a chip zooms to the place and opens its details. There is also a
  warning sign in the browser tab and an optional soft two-note chime.
- **Typhoons.** A swirl on the map for each tropical cyclone, labelled with its class (Tropical
  Depression, Tropical Storm, Severe Tropical Storm, Typhoon, Super Typhoon) and name. Selecting one
  shows how far its strong winds reach, where it is forecast to be in 24 hours, and only the
  airports within reach. A cyclone that only one source has reported is drawn grey and dashed and
  marked "not yet confirmed".
- **Focus on what is affected.** Selecting a volcano, an earthquake or a cyclone hides every airport
  except the ones it can affect (150 km ring for a volcano, 100 km ring for an earthquake, the
  strong-wind area for a cyclone). Closing the selection brings all airports back.
- **Nearest airport first.** On opening, the browser asks once for the viewer's location and shows
  the nearest airport. The location is used only in the browser and is not sent or stored.
- **Auto-show alerts.** With nobody using the screen, the map zooms to each earthquake alert, then
  each Danger airport, then returns to the whole map and repeats.
- **Fast earthquake watch.** Every 5 minutes a light check reads only the earthquake sources. A new
  strong earthquake triggers a full refresh and the alert at once, without waiting for the next
  scheduled refresh.
- **Volcanoes.** Triangles on the map for the monitored volcanoes, a brown dashed area for an official
  ash cloud warning, and a Volcano tab. Volcano alerts appear in the alert bar and the auto-show, and
  are sent by Teams and email.
- **Notifications by Teams and email** for the most critical events only: an airport at Danger, an
  earthquake alert, a possible tsunami, volcanic ash or an eruption, and a confirmed tropical storm
  or typhoon whose strong winds can reach an airport. Each is sent once; a typhoon alert is sent
  again when the cyclone moves up a class, and as an update (at most every 6 hours) when more
  airports come within reach.
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

## Volcano sources

| Role | Source | What it gives |
|---|---|---|
| Primary | Aviation volcanic ash warnings (SIGMET), aviationweather.gov | Eruption, and the area the ash covers |
| Second source | Tokyo Volcanic Ash Advisory Centre (Japan Meteorological Agency) | Eruption time, whether ash is seen, and an ash area when one is given |
| Alert levels, first choice | PHIVOLCS volcano bulletins | Alert Level 0 to 5 |
| Alert levels, backup | `volcano_levels.json`, entered by hand | Alert Level 0 to 5 |

When both ash sources report the same volcano, the aviation warning is used and the dashboard notes that Tokyo VAAC confirms it. When only Tokyo VAAC reports it, the alert is raised from the advisory and a notice says the second source is in use. If neither can be reached, the dashboard says volcano warnings are not available. The run log prints lines starting with `VAAC:` and `VOLCANO:` showing what each reader found.

## Map picture in alerts

Each Teams and email alert shows a small zoomed map of what it is about: the Danger airport, the volcano with its 150 km ring and the airports named in the warning, the earthquake with its nearest airport, or the cyclone with its strong-wind area, its 24-hour forecast position and the airports within reach. `alert_map.py` draws the picture when the alert is found, saves it under `docs/alertmaps/`, and the dashboard is published before the alert is sent so the picture is online. Pictures older than 7 days are removed. If the picture library (Pillow) cannot be installed, alerts are sent without a map. Set `SEND_MAPS = False` in `notify.py` to switch this off.

## How fast alerts arrive

Earthquake and volcano alerts are treated as critical.

- **Live Alert Watch (optional, not installed by default)** (`live_watch.py`, `.github/workflows/live-watch.yml`) looks once a minute at PHIVOLCS and USGS for earthquakes and at the official aviation volcanic ash warnings. When something new appears it refreshes the data, publishes the dashboard and sends the Teams and email alert, normally within about 3 minutes of the source publishing it.
- One run watches for about five and a half hours and then starts the next one. A 15-minute safety net restarts it if it ever stops.
- **Fallbacks:** the 5-minute Earthquake Watch (`quake_watch.py`) stands down while the live watch is running and takes over if it is not. The regular refresh also raises any alert it finds.
- **The dashboard page** asks USGS directly every minute for new earthquakes and checks for new data every 30 seconds.
- An alert can never be faster than its source. Volcano alerts come from the official aviation ash warning and the Tokyo VAAC advisory, which are issued some minutes after an eruption (11 minutes for Kanlaon on 10 October 2026).
- The live watch keeps one GitHub runner busy around the clock, so it is left out unless it is added on purpose. Without it, the 5-minute Earthquake Watch raises these alerts, typically 5 to 15 minutes after the source.

## Where the data comes from

| Data | First choice | Backup |
|---|---|---|
| Airport reports and forecasts (issued by PAGASA) | aviationweather.gov | NOAA data server (same reports) |
| Estimates (airports with no official report) | MET Norway | Open-Meteo |
| Chance of rain and the 7-day outlook | Open-Meteo | none; the items are left out |
| Tropical cyclones (typhoons) | Three sources read at every check: aviation storm warnings (aviationweather.gov) for position, movement and warning areas; RSMC Tokyo (Japan Meteorological Agency) for strength, wind reach and the 24-hour forecast; GDACS as an independent third | Each stands in for the others. A cyclone is confirmed only when at least two report it |
| Thunderstorm area warnings | Aviation storm warnings (aviationweather.gov) | none |
| Earthquakes | PHIVOLCS | USGS, then EMSC. Every earthquake of magnitude 5.0 or stronger is also cross-checked against USGS or EMSC |
| Volcanic ash and eruptions | Aviation ash warnings (SIGMET), aviationweather.gov. Gives the ash area | Second source: Tokyo VAAC advisories (Japan Meteorological Agency). Confirms the warning, and stands in when it is missing or cannot be reached |
| Volcano alert levels | PHIVOLCS volcano bulletins | Levels entered by hand in `volcano_levels.json` |
| Rain on the map | MET Norway forecast grid | none |
| Detailed rain map (optional) | Windy.com embedded map | none |

Accuracy ranking, highest first: official airport report, official airport forecast, official
aviation area warning, computer forecast estimate. When sources differ, the higher-ranked one is
used. Idle backups are tested every 6 hours and the result is shown in Help.

## How readings are checked before they are shown or sent

The dashboard is read by station staff, management and CAAP, so every reading says where it came
from and whether a second source agrees.

| Kind | What is compared | Rule |
|---|---|---|
| Airport weather | One official report exists per airport, so it is checked for age. It can be read from two servers | Danger is raised only from the official report, never from an Estimate. A report older than 90 minutes lowers the Confidence |
| Earthquakes | PHIVOLCS against USGS and EMSC | Shown and sent as soon as the first agency reports, because minutes matter. Each one of magnitude 5.0 or stronger carries a Cross-check line: confirmed by a second agency, not yet confirmed, or could not be cross-checked |
| Volcanic ash and eruptions | Aviation ash warning against the Tokyo VAAC advisory | Sent as soon as either official source reports. The details say whether Tokyo VAAC has confirmed it |
| Tropical cyclones | Aviation storm warnings, RSMC Tokyo and GDACS | An alert is raised only after two of the three agree. Until then the cyclone is listed as "not yet confirmed" |

If a source is down its backup is used and a yellow notice says so. A reading that could not be
cross-checked says so in plain words; it is never shown as confirmed.

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
- **Typhoon classes** follow PAGASA, using winds averaged over 10 minutes: Tropical Depression up to
  61 km/h, Tropical Storm 62 to 88, Severe Tropical Storm 89 to 117, Typhoon 118 to 184, Super
  Typhoon 185 or more. GDACS measures over 1 minute, which reads higher, so its figure is shown for
  comparison only.
- **A confirmed cyclone** is reported by at least two of the three sources: the same name within
  1,000 km, or positions within 300 km of each other.
- **Typhoon alert:** a confirmed Tropical Storm or stronger whose strong winds (about 55 km/h or
  more, the RSMC Tokyo 30-knot wind radius) can reach an airport now, or will at its forecast
  position 24 hours ahead. When the wind reach is not reported, 300 km from the centre is used
  (`TY_NEAR_KM` in `build.py`). A Tropical Depression is shown but raises no alert.
- **Why that rule.** PAGASA raises Wind Signal No. 1 when winds of 39 to 61 km/h are expected within
  36 hours and No. 2 (62 to 88 km/h) within 24 hours, and CAAP Memorandum Circular 013-2023 restricts
  flights by aircraft of 5,700 kg and below in areas under Signal No. 1. Wind signals are not
  published as data, so the measured reach of strong winds and the 24-hour forecast are used as the
  nearest equivalent. The Safety office should confirm this rule; PAGASA's signal remains the
  official one.
- **Volcanoes** raise their own alerts, like earthquakes, and never change an airport's weather level.
  A volcano counts as near an airport within 150 km (no official standard exists; this covers about
  half of past airport disruptions in a US Geological Survey study).
- **Volcanic ash alert:** an official ash area covers an airport, at any distance. The area comes from
  the aviation ash warning, or from the Tokyo VAAC advisory when there is no warning.
- **Eruption alert:** an aviation ash warning or a Tokyo VAAC advisory reports an eruption within
  150 km of an airport. A Tokyo VAAC advisory counts for 6 hours after it is issued (`VAAC_HOURS`).
- **Volcano Alert Level** (PHIVOLCS, 0 to 5): Level 3 or higher within 150 km of an airport raises an
  alert on the dashboard.
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
- PAGASA's public typhoon bulletins and wind signals are not published as data, so they are not read
  directly. The typhoon alert is based on measured wind reach, not on the wind signal. Confirm
  typhoon decisions against PAGASA and CAAP advisories.
- Low pressure areas are not shown: no reliable public data source was found, so a cyclone first
  appears when it becomes a Tropical Depression.

## Data credits

Weather and earthquake data belong to their publishers: PAGASA, the US Aviation Weather Center and
NOAA, the Norwegian Meteorological Institute (MET Norway), Open-Meteo, GDACS, PHIVOLCS, USGS and
EMSC. The optional detailed rain map is provided by Windy.com.

## Copyright

© 2026 1Aviation Groundhandling Services, Corp. All rights reserved.

Developed by the 1AV IT Department. Created under 1AV IT Innovation by Jake V Borras.
