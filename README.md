# 1AV Disruption Management Dashboard

A dashboard by 1Aviation Groundhandling Services, Corp. for the 36 Philippine airports served by
Cebu Pacific and Cebgo. It shows, on one screen, which airports may be affected by weather,
earthquakes, volcanoes or typhoons, and what staff should do.

## What it shows

- **Airport weather.** Each airport is marked by its current level, from Normal to Danger.
- **Earthquakes.** Recent earthquakes in and around the Philippines, and which airports are near them.
- **Volcanoes.** Volcano status, ash clouds and where the ash is heading.
- **Typhoons.** Where each typhoon is, how far its strong winds reach, and where it is expected to go.
- **Rain forecast.** The expected rain for the next 24 hours, played on the map.
- **Official updates and news.** The latest advisories, news and videos about the selected airport or event, from national
  and local newsrooms and the transport and airport authorities, sorted into Disruption reported, Disruption possible and
  For awareness. Strikes, protests, road closures, traffic and holidays are included.
- **Holidays and planned events.** National holidays for the next 7 days, and local events the team enters in `events.json`.
- **Flights.** Cebu Pacific and Cebgo aircraft, so staff can see which flights are heading into bad weather.

## Alert levels

| Level | Meaning | What staff do |
|---|---|---|
| Normal | No bad weather expected today | No action needed |
| Advisory | Bad weather expected later today | Plan ramp work around it |
| Warning | Bad weather within 1 hour, or already happening | Be ready to pause ramp work |
| Danger | A thunderstorm is at the airport now | Work at the ramp with extra care. Safety comes first |

Earthquakes, volcanoes and typhoons have their own alerts.

## How it works

1. The dashboard regularly collects the latest information from official and trusted public sources,
   such as PAGASA and PHIVOLCS.
2. Important readings are checked against a second source before they are treated as confirmed.
3. It updates by itself, so there is no need to reload the page.
4. The most critical alerts are also sent to Microsoft Teams and by email.

## How to use it

- Select any airport, earthquake, volcano or typhoon on the map to see its details.
- Use the alert button at the top to see all current alerts.
- Use **Layers** to turn parts of the map on or off.
- Press the **?** button for a full guide.

## Pages (view only)

- `airport.html?id=<airport id>`: one airport's full page: today, hour by hour with heat index, the next 7 days,
  the last 30 days, hazards in reach, and news.
- `event.html?id=v:<volcano>`, `t:<typhoon>` or `q:<earthquake>`: map, affected airports and timeline of one event.
- `report.html`: the monthly disruption report.

The pages have no download, email or share controls. The monthly report and the "last 30 days" figures come from
`docs/history/`, a small daily record the update adds to each time it runs (one file per month).

## Adding local holidays, strikes and road closures

Open `events.json`, copy the example event, and fill in the title, the start date (and end date if longer than a day), and
the airports it affects (their ids are listed in the file; leave the list empty for all airports). Save the file. The event
shows on the dashboard for the 7 days before it and disappears by itself after it ends.

## Please note

This dashboard supports decisions. It does not replace official bulletins from PAGASA, PHIVOLCS
and CAAP, or the judgement of staff at the airport.

## Copyright

© 2026 1Aviation Groundhandling Services, Corp. All rights reserved. For internal use.

Developed by the 1AV IT Department. Created under 1AV IT Innovation by Jake V Borras.
