# 1AV Airport Weather Monitoring

A view-only dashboard for the 36 Philippine airports served by Cebu Pacific and Cebgo.
It is hosted free on GitHub Pages and refreshes its own data about every 10 minutes.

## How it works

| Part | What it does |
|---|---|
| `build.py` | Pulls the data, applies the alert rules, writes `docs/data.json`. Python standard library only. |
| `docs/index.html` | The dashboard page. Reads `data.json` and checks for new data every 5 minutes. |
| `docs/rain.json` | Hour-by-hour rain forecast grid for the moving rain layer. Rebuilt by `build.py` every 3 hours. |
| `docs/assets/` | Map image and 1AV logo. |
| `.github/workflows/refresh.yml` | Runs `build.py` every 10 minutes on GitHub and saves the new `data.json`. |

## Sources and backups

For each kind of data the script uses the first source that answers and keeps the others as backups.
The order is the `SOURCE_ORDER` table near the top of `build.py`; change it there.

| Data | First choice | Backup |
|---|---|---|
| Airport reports and forecasts | aviationweather.gov | NOAA data server (tgftp.nws.noaa.gov), same official reports |
| Estimates (no official report) | MET Norway (api.met.no) | Open-Meteo (api.open-meteo.com) |
| Typhoon watch | Aviation storm warnings (aviationweather.gov) | GDACS (gdacs.org), position only |
| Earthquakes | PHIVOLCS | USGS, then EMSC |

The help window (the ? at the top of the page) shows which source supplied each kind of data at the
latest check, and a yellow notice appears on the page whenever a backup is in use. No keys or accounts are needed.

Things to know about the sources:

- **PHIVOLCS** has no data feed, so the script reads the earthquake table on its public web page.
  If PHIVOLCS changes that page, the reading fails a built-in safety check and USGS takes over.
  The PHIVOLCS site sometimes has an incomplete security certificate; for that site only, the script
  retries without certificate checking.
- **PHIVOLCS and USGS often give slightly different magnitudes** for the same earthquake. The
  4.5 and 5.0 rules are applied to whichever source is in use.
- **Open-Meteo** is free for non-commercial use only. It is used only when MET Norway is down. If
  company policy requires it, remove `'openmeteo'` from `SOURCE_ORDER` or buy their commercial plan.
- **The moving rain layer** on the airport map plays by itself through the next 24 hours. The rain is a
  MET Norway computer forecast sampled on a grid of 368 points (about 80 km apart), so it shows broad
  rain areas, not street-level detail. It is rebuilt every 3 hours (`RAIN_EVERY_HOURS` in `build.py`),
  which adds about a minute to that run. MET Norway has no thunder forecast for the Philippines, so the
  lightning marks come from official sources instead: aviation thunderstorm area warnings and the
  official airport forecasts. The layer plays no part in the alert levels.
- **Windy.com** supplies an optional, more detailed map lower on the page. It loads only when a viewer
  presses "Show Windy map". Check Windy's embed terms for company use.
- **PAGASA** is the official typhoon authority for the Philippines but publishes no data feed, so it
  is not used. Always confirm typhoon decisions against PAGASA bulletins.

## Set up (about 10 minutes)

1. **Create the repository.** On github.com choose **New repository**. Name it, for example,
   `airport-weather`. Set it to **Public** (free GitHub Pages needs a public repository).
2. **Upload the files.** Open the new repository, choose **uploading an existing file**, and drag in
   everything from this folder, keeping the folders as they are. Commit.
   - If the `.github` folder does not upload (some computers hide folders that start with a dot),
     choose **Add file > Create new file**, type the name `.github/workflows/refresh.yml`,
     paste the contents of that file, and commit.
3. **Allow the refresh to save data.** Go to **Settings > Actions > General > Workflow permissions**,
   choose **Read and write permissions**, and save.
4. **Turn on the website.** Go to **Settings > Pages**. Under **Build and deployment** set
   **Source** to **Deploy from a branch**, branch **main**, folder **/docs**, and save.
5. **Run the first refresh.** Go to the **Actions** tab, enable workflows if asked, open
   **Refresh dashboard data**, and press **Run workflow**.
6. **Open the dashboard.** After a minute or two it is live at
   `https://YOUR-USERNAME.github.io/airport-weather/`. Share that address.

## Day to day

- Nothing to do. The refresh runs by itself every 10 minutes.
- GitHub sometimes starts scheduled runs late. If the data is more than 60 minutes old, the page
  shows a yellow "Data may be out of date" notice by itself.
- If a source cannot be reached, the page says so in a notice and keeps working with the rest.
- GitHub pauses scheduled runs in a repository with no activity for 60 days. The refresh saves data
  regularly, which counts as activity, so this should not happen. If it ever does, open the
  **Actions** tab and re-enable the workflow.

## Run it on your own PC instead

```
python3 build.py
python3 -m http.server 8080 --directory docs --bind 0.0.0.0
```

Then open `http://localhost:8080`, or `http://YOUR-PC-ADDRESS:8080` from another device on the same
network. Run `build.py` again (or schedule it) to refresh the data.

## Changing things

- **Refresh interval:** the `cron` line in `.github/workflows/refresh.yml`.
- **Airports:** the `APTS` table near the top of `build.py`.
- **Alert rules and wording:** `build.py`. The page only displays what `data.json` contains.
- **Look and layout:** `docs/index.html`.

## Limits

- The page is public: anyone with the address can view it.
- Estimates show rain and wind only and can never be Danger.
- Earthquakes cannot be predicted; only past ones are shown.
- The dashboard supports decisions. It does not replace official bulletins or on-site judgment.
