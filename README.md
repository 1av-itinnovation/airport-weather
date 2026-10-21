# 1AV Disruption Management Dashboard

A view-only dashboard for the 36 Philippine airports served by Cebu Pacific and Cebgo. It watches the
weather at each airport, and the earthquakes, volcanoes and typhoons that can affect them. It shows
which airports need attention, why, and what to do.

Every figure names its source. Critical readings are checked against a second source before they are
called confirmed. The Help button (?) on the dashboard explains the same things for viewers.

## Contents

1. [Alert levels](#alert-levels)
2. [What the dashboard shows](#what-the-dashboard-shows)
3. [How it works](#how-it-works)
4. [Where the data comes from](#where-the-data-comes-from)
5. [How readings are checked](#how-readings-are-checked)
6. [The rules](#the-rules)
7. [Alerts by Teams and email](#alerts-by-teams-and-email)
8. [Files in this repository](#files-in-this-repository)
9. [Settings](#settings)
10. [What it cannot do](#what-it-cannot-do)

## Alert levels

| Level | Meaning | What staff do |
|---|---|---|
| Normal | No bad weather expected today | No action needed |
| Advisory | Bad weather expected later today | Plan ramp work around it |
| Warning | Bad weather within 1 hour, or already happening | Be ready to pause ramp work |
| Danger | A thunderstorm is at the airport now | Work at the ramp with extra care. Safety comes first |

Levels describe the weather only. Earthquakes, volcanoes and typhoons raise their own alerts and do
not change an airport's level.

## What the dashboard shows

**The screen**

| Part | What it does |
|---|---|
| Map | Airports as dots coloured by level. Flashing dot: thunderstorm now. Dashed outline: Estimate |
| Airport list | Airports at the chosen level, with what to expect and when |
| Tiles | Counts at each level and key figures. Pressing one filters the map and the list |
| Today and Tomorrow | Switches between today's alerts and tomorrow's forecast |
| Region and Find an airport | Narrows to Luzon, Visayas or Mindanao, or jumps to one airport |
| Layers | Turns rain, earthquakes, all volcanoes and all airport names on or off |
| Hazards | Full lists of earthquakes, volcanoes, typhoons and low pressure areas |
| Alert button | Shows active alerts with a count, newest at the top. New alerts appear briefly, then tuck away |
| Colours, sound, help | Auto, Day or Night colours; an optional soft chime; the Help guide |
| Phone layout | Map, list and details become three tabs |

**The map**

- **Usual view:** the Philippine Area of Responsibility (PAR), drawn as a dashed outline. Viewers can
  zoom out and drag further. Neighbouring countries are drawn for reference only.
- **Rain timeline:** plays the forecast rain for the next 24 hours, with pause and a slider.
  Each typhoon moves with it, to where RSMC Tokyo forecasts its centre at that hour; a small dashed
  ring stays at its last reported position.
  Lightning marks come only from official thunderstorm warnings and airport forecasts.
- **Marks:** purple rings for earthquakes, small purple dots for weaker ones, triangles for volcanoes,
  a brown area for an official ash cloud, a swirl for a tropical cyclone, a red L for a low pressure area.
- **Returns to where you were:** closing a selection restores the previous zoom.
- **Auto-show:** with nobody using the screen, the map visits each alert in turn: earthquakes, volcanoes,
  typhoons inside the PAR, then Danger airports. If a news video from the last 24 hours is about a place
  on show, the most important one (flights or airport first, then newest) plays muted at the top of the
  details panel (never over the map), at most once every 2 hours, and the round carries on when it ends.
- **Windy map:** an optional, more detailed rain map from Windy.com.

**Selecting something**

| Selected | On the map | In the details |
|---|---|---|
| Airport | Close-up box: runway at its true direction, wind arrow, 5 km and 10 km rings | Banner, what to do, wind, gusts, visibility, lowest cloud, crosswind and headwind, forecast for later today, rain for the next 12 hours, news from the last 24 hours, tomorrow and the week ahead, source |
| Earthquake | Rings at 25, 50 and 100 km. Airports inside 100 km with their distances | Magnitude, exact time, depth, nearest airport, tsunami note, aftershocks, cross-check |
| Volcano | 150 km ring, ash cloud, direction arrow, forecast ash outlines with times, airport distances | Eruption time, ash warning, where the ash is heading, Alert Level, airports nearby |
| Typhoon | Strong-wind ring, storm-force ring, forecast track and cone for up to 5 days. Airports marked "now" or "within 24 h" | Class, winds, position, airports within reach, cross-check |
| Low pressure area | Its position | Chance of becoming a cyclone. Information only |

Notes on the airport view:

- **Banner.** One line drawing used for every airport. Only the sky colour and a light effect change
  with the main condition. When several apply, the most serious is shown. Movement stops when the
  device asks for reduced motion.
- **Crosswind and headwind.** Worked out from the reported wind direction and the stronger of wind or
  gusts, for the runway end facing the wind. A guide for ground staff only. Not shown when the wind is
  calm or variable, or for an Estimate.
- **In the news.** Headlines from the last 24 hours from GMA News, ABS-CBN News, TV5 and CNN, newest
  first. A story is shown only if it names the airport's place and is about flights or a hazard
  there; it is tagged "Flights or airport" or "Hazard in the area". Only the headline, a short summary,
  the publisher's thumbnail and a link are kept; the story stays on the publisher's site. News never
  changes an alert level. Stories are listed most critical first (flights or airport, then the event, then the area;
  newest first within each). Selecting an airport or event plays its most critical video at once,
  muted, at the top of the details panel, and closing the selection stops it. Other videos have a
  "Play video here" button; the video
  plays in the publisher's YouTube player. The refresh opens at most 12 story pages to find their videos.
- **News for events.** Earthquakes, volcanoes and typhoons have the same news section. A story is
  linked by the volcano's name, the typhoon's international or PAGASA name, or for an earthquake the
  place or the magnitude, published after it happened. Tagged "About this event".
- **Estimates.** Airports with no official report show wind, rain, cloud cover and temperature from a
  computer forecast, and are marked Estimate.

## How it works

The dashboard is a static website on GitHub Pages. GitHub Actions refreshes its data on a schedule.
There is no server and no database.

| Step | What happens | Where |
|---|---|---|
| 1. Collect | Reads the latest public data from each source | `build.py` |
| 2. Choose | Uses the first-choice source; switches to a backup if it cannot be reached | `build.py` |
| 3. Apply the rules | Works out levels, forecasts, hazard alerts and cross-checks | `build.py` |
| 4. Save | Writes the result for the page to read | `docs/data.json` |
| 5. Publish | The website is updated first, so alert pictures are online | GitHub Pages |
| 6. Alert | Sends new critical alerts to Teams and email, once each | `notify.py`, `alert_map.py` |
| 7. Show | The page reads the data and checks for newer data by itself | `docs/index.html` |

**How often**

| Job | Schedule | Purpose |
|---|---|---|
| Refresh (`refresh.yml`) | Asked every 10 minutes; GitHub runs it about every 20 to 25 | Full update of all data |
| Earthquake watch (`quake-watch.yml`) | Every 5 minutes | Light check for earthquakes and ash warnings. A new one triggers a full refresh at once |
| Rain layer | Every 3 hours, inside the refresh | Rebuilds the moving rain forecast |
| Backup tests | Every 6 hours, inside the refresh | Confirms idle backups still work |
| Open page | By itself | Asks USGS for new earthquakes every minute and loads newer data when it is published. No reload needed |

**How the forecasts are made**

- **Today.** The official airport report says what is happening now. The official airport forecast
  says what is expected in the hours ahead. The level comes from these two.
- **No official report.** A computer forecast for the airport's location stands in, marked Estimate.
- **Rain by the hour and the week ahead.** A computer forecast, for planning only. It never changes a level.
- **Rain on the map.** A forecast sampled on a grid across the region and played as a timeline.
- **Typhoon track.** RSMC Tokyo's forecast positions at 24, 48, 72, 96 and 120 hours.
- **Ash forecast.** Tokyo VAAC's expected ash areas at about 6, 12 and 18 hours.

## Where the data comes from

| Data | First choice | Backup |
|---|---|---|
| Airport reports and forecasts (issued by PAGASA) | aviationweather.gov | NOAA data server |
| Estimates | MET Norway | Open-Meteo |
| Rain chance and the week ahead | Open-Meteo | None; the items are left out |
| Typhoons | Aviation storm warnings, RSMC Tokyo (Japan Meteorological Agency) and GDACS, all three at every check | Each stands in for the others |
| Thunderstorm area warnings | Aviation storm warnings | None |
| Low pressure areas | Joint Typhoon Warning Center | None; the marks are left out |
| Earthquakes | PHIVOLCS | USGS, then EMSC |
| Volcanic ash and eruptions | Aviation ash warnings (SIGMET) | Tokyo Volcanic Ash Advisory Centre (VAAC) |
| Volcano Alert Levels | PHIVOLCS bulletins | `volcano_levels.json`, entered by hand |
| PAGASA typhoon names | PAGASA bulletin pages | `typhoon_names.json`, entered by hand |
| Rain on the map | MET Norway | None |
| Runways | OurAirports, stored in `runways.json` | None |
| News | Public news feeds of GMA News, ABS-CBN News, TV5 and CNN International (CNN Philippines closed in 2024) | A Google News search limited to the same newsroom's site |

When sources differ, the more reliable one is used, in this order: official airport report, official
airport forecast, official area warning, Estimate.

## How readings are checked

| Kind | What is compared | Rule |
|---|---|---|
| Airport weather | One official report per airport, checked for age | Danger only from the official report. Older than 90 minutes lowers the confidence shown |
| Earthquakes | PHIVOLCS against USGS and EMSC | Shown at once. A Cross-check line says whether a second agency agrees |
| Volcanoes | Aviation ash warning against Tokyo VAAC | Shown as soon as either reports. The details say whether the second confirms it |
| Typhoons | Three sources | An alert needs two of the three to agree. Otherwise "Not yet confirmed" |

If a source is down, its backup is used and a yellow notice says so. A reading that could not be
cross-checked says so. It is never shown as confirmed.

## The rules

**Weather**

| Rule | Value |
|---|---|
| Danger | An official airport report says a thunderstorm is at the airport now. Never from an Estimate |
| Bad weather | Thunderstorm, rain or rain showers, or strong winds |
| Bad weather in an Estimate | 2.5 mm or more of rain in an hour, or winds of 39 km/h or more |
| Rain | Light under 2.5 mm an hour. Moderate 2.5 mm or more. Heavy 7.6 mm or more |
| Area warnings | An airport inside an official thunderstorm or cyclone warning area is raised to Warning |
| "Possible at times" | The weather may come and go. "Expected" means the forecast is firm |

**Earthquakes**

| Rule | Value |
|---|---|
| Shown as rings | Magnitude 4.5 or stronger, past 7 days |
| Shown as dots | Magnitude 3.0 to 4.4, past 3 days. No alert |
| Alert | 4.5 or stronger within 100 km of an airport, or 6.0 or stronger anywhere in the Philippine area, in the last 24 hours |
| Possible tsunami | 6.5 or stronger and no deeper than 70 km, or flagged by USGS. A prompt to check PHIVOLCS, not an official warning |
| Aftershocks | Below 4.5, within 100 km and 72 hours of a main earthquake of 5.0 or stronger. Grouped with it |
| Two agencies | For strong earthquakes, the more cautious of the two positions decides the 100 km test |

**Typhoons**

| Rule | Value |
|---|---|
| Classes (PAGASA, km/h) | Tropical Depression up to 61. Tropical Storm 62 to 88. Severe Tropical Storm 89 to 117. Typhoon 118 to 184. Super Typhoon 185 or more |
| Confirmed | Two of three sources: the same name within 1,000 km, or positions within 300 km |
| Alert | A confirmed Tropical Storm or stronger whose strong winds (about 55 km/h or more) can reach an airport now, or at its forecast position 24 hours ahead |
| Wind reach not reported | 300 km from the centre is used |
| Name | Inside the PAR: the PAGASA name with the international name after it, for example "Typhoon Pepito (Man-yi)". Outside: the international name |
| Basis | PAGASA wind signals and CAAP Memorandum Circular 013-2023. Wind signals are not published as data, so measured wind reach is the nearest equivalent. PAGASA's signal remains the official one |

**Volcanoes**

| Rule | Value |
|---|---|
| Near an airport | Within 150 km. No official standard exists; this covers about half of past airport disruptions (US Geological Survey study) |
| Ash alert | An official ash area covers an airport, at any distance |
| Eruption alert | An eruption is reported within 150 km of an airport. A Tokyo VAAC advisory counts for 6 hours |
| Alert Level | PHIVOLCS scale, 0 to 5. Level 3 or higher within 150 km is flagged on the dashboard |
| Ash forecast | For planning only. It raises no alert |

The Safety office should confirm the typhoon rule and the 100 km and 150 km distances.

## Alerts by Teams and email

Only the most critical events are sent. Every alert starts with its **alert level**, so readers
know at once how serious it is. The subject line starts with the highest level in the message,
for example `[DANGER] Disruption Management: ...`.

| Alert level | Means | Used for |
|---|---|---|
| Danger | Act now | Thunderstorm at an airport; possible tsunami; M6.0 or stronger within 100 km of an airport; ash over an airport; typhoon winds that can reach an airport now |
| Warning | Prepare | Any other earthquake alert; an eruption within 150 km; a raised volcano Alert Level; typhoon winds expected within 24 hours |

| Alert | Sent when | Sent again |
|---|---|---|
| Thunderstorm | An airport reaches Danger | If it leaves Danger and returns after 3 hours |
| Earthquake or possible tsunami | It meets the earthquake alert rule | No |
| Volcanic ash or eruption | It meets the volcano alert rules | Not within 12 hours for the same alert |
| Typhoon | It meets the typhoon alert rule | When it moves up a class; as an update when more airports come within reach, at most every 6 hours |

Each alert carries what the dashboard shows when the same thing is selected:

- **Thunderstorm:** the airport close-up, and rows for wind, visibility, lowest cloud and crosswind.
- **Earthquake:** the 25, 50 and 100 km rings, and every airport within 100 km with its distance.
- **Volcano:** the direction arrow, forecast ash outlines, airport distances, and where the ash is heading.
- **Typhoon:** the strong-wind and storm-force rings, and airports marked "now" or "within 24 h".

How it is sent:

- `notify.py` posts to a Power Automate flow, which sends the Teams card and the email. The flow
  address is kept as the repository secret `ALERT_WEBHOOK_URL`. It is never written in a file.
- `alert_map.py` draws the map picture and saves it under `docs/alertmaps/`. Pictures older than
  7 days are removed.
- Before sending, `notify.py` confirms the website is serving the exact picture just drawn. If not,
  the alert goes without a picture.
- `notify_state.json` records what has been sent, so nothing is sent twice.
- Earthquake alerts give the time to the second, with UTC beside it. Volcano alerts give the eruption
  time from the Tokyo VAAC advisory, or say that no official source has published it.

## Files in this repository

| File | Purpose |
|---|---|
| `build.py` | Collects the data, applies the rules, writes `docs/data.json` and `docs/rain.json` |
| `notify.py` | Finds new alerts and sends them to Teams and email |
| `alert_map.py` | Draws the map picture for each alert |
| `quake_watch.py` | The 5-minute check for earthquakes and ash warnings |
| `runways.json` | Runway positions and directions for the 36 airports |
| `volcano_levels.json` | Volcano Alert Levels entered by hand, used when PHIVOLCS cannot be read |
| `typhoon_names.json` | PAGASA local names entered by hand, used when the PAGASA bulletin cannot be read |
| `notify_state.json` | Record of alerts already sent. Do not delete it |
| `docs/index.html` | The dashboard page |
| `docs/data.json`, `docs/rain.json` | The data the page reads. Written by the refresh |
| `docs/assets/` | Map drawings, logo and pictures used by the page and the Teams card |
| `docs/alertmaps/` | Map pictures for alerts |
| `.github/workflows/` | The schedules: `refresh.yml` and `quake-watch.yml` |

The run log of each refresh shows what every reader found. Lines start with a label such as
`TYPHOON:`, `VAAC:`, `VOLCANO:` or `NEWS:`.

## Settings

The main values can be changed at the top of the files.

| Setting | File | Default | Meaning |
|---|---|---|---|
| `ALERT_MAG` | `build.py` | 4.5 | Smallest earthquake that can raise an alert |
| `SMALL_MAG`, `SMALL_DAYS` | `build.py` | 3.0, 3 | Weaker earthquakes shown as dots, and for how long |
| `TY_NEAR_KM` | `build.py` | 300 | Distance used when a typhoon's wind reach is not reported |
| `VOLC_KM` | `build.py` | 150 | How near a volcano counts as near an airport |
| `VAAC_HOURS` | `build.py` | 6 | How long a Tokyo VAAC advisory counts |
| `SEND_MAPS` | `notify.py` | On | Map pictures in alerts |
| `SEND_VOLCANO`, `SEND_TYPHOON` | `notify.py` | On | Volcano and typhoon alerts |
| `SEND_VOLCANO_LEVEL` | `notify.py` | Off | Alerts for Alert Level 3 or higher |
| `SEND_HEADSUP`, `SEND_BRIEFING` | `notify.py` | Off | Advance notices and twice-daily briefings |
| `WATCH_MAG` | `quake_watch.py` | 4.5 | Smallest earthquake the 5-minute check reacts to |
| `NEWS_SOURCES` | `build.py` | GMA, ABS-CBN, TV5, CNN | Newsrooms read for airport news, each with its feed addresses |
| `NEWS_PLACES` | `build.py` | One per airport | The place names that link a story to an airport |
| `NEWS_HOURS`, `NEWS_MAX` | `build.py` | 24, 8 | How far back news goes, and how many stories per airport |
| `NEWS_PAGE_FETCH` | `build.py` | 12 | Story pages opened per refresh to find a story's video |
| `VID_MAX_MS`, `VID_AGAIN_MS` | `docs/index.html` | 150 s, 2 h | Longest auto-played video, and how soon the same video can play again |

## What it cannot do

- It supports decisions. It does not replace official bulletins, official tsunami warnings, or the
  judgement of staff at the airport.
- It does not detect lightning. Thunderstorm information comes from official reports, forecasts and warnings.
- An Estimate shows rain and wind only. It cannot confirm a thunderstorm.
- Earthquakes cannot be predicted, and no source is instant. Agencies usually publish 5 to 20 minutes
  after the event, and first magnitudes are often revised.
- An alert cannot be faster than its source and the schedule. Expect 5 to 15 minutes after the source publishes.
- Forecasts for tomorrow and beyond are less certain than today.
- PAGASA typhoon bulletins and wind signals are not published as data, so they are not read directly.
  Confirm typhoon decisions against PAGASA and CAAP advisories.
- Low pressure areas come from one source and the list is not complete. PAGASA's outlook is the official one.
- Crosswind figures are a guide for ground staff. Flight crews and the tower use their own.
- News is picked by place and topic words, so an unrelated story can slip in or a relevant one be missed.
  Read the story before acting on it.

## Data credits

Data belongs to its publishers: PAGASA, the US Aviation Weather Center and NOAA, MET Norway,
Open-Meteo, the Japan Meteorological Agency (RSMC Tokyo and Tokyo VAAC), GDACS, the Joint Typhoon
Warning Center, PHIVOLCS, USGS, EMSC and OurAirports. Headlines belong to GMA News, ABS-CBN News
and TV5, and link to their sites. The optional detailed rain map is by Windy.com.

## Copyright

© 2026 1Aviation Groundhandling Services, Corp. All rights reserved.

Developed by the 1AV IT Department. Created under 1AV IT Innovation by Jake V Borras.
