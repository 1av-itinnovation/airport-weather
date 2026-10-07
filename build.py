#!/usr/bin/env python3
"""
1AV Airport Weather Monitoring - data builder.

Copyright (c) 2026 1Aviation Groundhandling Services, Corp. All rights reserved.
Created under 1AV IT Innovation by Jake V Borras.

Pulls public weather and earthquake data, applies the dashboard's alert rules,
and writes docs/data.json, which docs/index.html reads.

Sources (all public, no key needed). For each kind of data the first source that answers is used;
the others are backups. The order is set in SOURCE_ORDER below.
  Airport reports and forecasts   1) aviationweather.gov   2) NOAA data server (tgftp.nws.noaa.gov)
  Estimates (no official report)  1) MET Norway (api.met.no)   2) Open-Meteo (api.open-meteo.com)
  Typhoon watch                   1) Aviation storm warnings (aviationweather.gov)   2) GDACS (gdacs.org)
  Earthquakes                     1) PHIVOLCS   2) USGS   3) EMSC

Uses only the Python standard library. Run:  python3 build.py
"""
import json, re, math, os, sys, time, datetime as dt
import urllib.request, ssl
from collections import Counter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs', 'data.json')
CONTACT = os.environ.get('GITHUB_REPOSITORY', 'airport-weather-dashboard')
UA = f'1AV-AirportWeatherDashboard/1.0 (https://github.com/{CONTACT})'

# id, ICAO code, display name, region, latitude, longitude, map x %, map y %
APTS = [
    ('bacolod', 'RPVB', 'Bacolod', 'visayas', 10.7764, 123.015, 61.0, 61.7),
    ('boholpanglao', 'RPSP', 'Bohol (Panglao)', 'visayas', 9.573, 123.77, 67.6, 68.8),
    ('busuangacoron', 'RPVV', 'Busuanga (Coron)', 'luzon', 12.1215, 120.1, 35.7, 53.7),
    ('butuan', 'RPME', 'Butuan', 'mindanao', 8.9515, 125.4788, 82.4, 72.5),
    ('cagayandeoro', 'RPMY', 'Cagayan de Oro', 'mindanao', 8.6122, 124.4565, 73.5, 74.5),
    ('calbayog', 'RPVC', 'Calbayog', 'visayas', 12.0727, 124.545, 74.3, 54.0),
    ('camiguin', 'RPMH', 'Camiguin', 'mindanao', 9.2535, 124.707, 75.7, 70.7),
    ('caticlanboracay', 'RPVE', 'Caticlan (Boracay)', 'visayas', 11.9245, 121.954, 51.8, 54.9),
    ('cauayan', 'RPUY', 'Cauayan', 'luzon', 16.9299, 121.753, 50.0, 25.3),
    ('cebumactan', 'RPVM', 'Cebu (Mactan)', 'visayas', 10.3075, 123.9783, 69.4, 64.4),
    ('clark', 'RPLC', 'Clark', 'luzon', 15.1872, 120.5623, 39.7, 35.6),
    ('davao', 'RPMD', 'Davao', 'mindanao', 7.1261, 125.6454, 83.9, 83.3),
    ('dipolog', 'RPMG', 'Dipolog', 'mindanao', 8.602, 123.342, 63.8, 74.6),
    ('dumaguete', 'RPVD', 'Dumaguete', 'visayas', 9.3343, 123.2985, 63.5, 70.2),
    ('elnido', 'RPEN', 'El Nido', 'luzon', 11.2025, 119.417, 29.7, 59.2),
    ('generalsantos', 'RPMR', 'General Santos', 'mindanao', 6.0569, 125.0965, 79.1, 89.6),
    ('iloilo', 'RPVI', 'Iloilo', 'visayas', 10.833, 122.4934, 56.5, 61.3),
    ('kalibo', 'RPVK', 'Kalibo', 'visayas', 11.6833, 122.3835, 55.4, 56.3),
    ('laoag', 'RPLI', 'Laoag', 'luzon', 18.1786, 120.5312, 39.4, 17.9),
    ('legazpibicol', 'RPLK', 'Legazpi (Bicol)', 'luzon', 13.1113, 123.677, 66.8, 47.9),
    ('manilanaia', 'RPLL', 'Manila (NAIA)', 'luzon', 14.5078, 121.0156, 43.7, 39.6),
    ('masbate', 'RPVJ', 'Masbate', 'luzon', 12.3694, 123.629, 66.3, 52.3),
    ('naga', 'RPUN', 'Naga', 'luzon', 13.5849, 123.27, 63.2, 45.1),
    ('ozamiz', 'RPMO', 'Ozamiz', 'mindanao', 8.1785, 123.842, 68.2, 77.1),
    ('pagadian', 'RPMP', 'Pagadian', 'mindanao', 7.8307, 123.4612, 64.9, 79.1),
    ('puertoprincesa', 'RPVP', 'Puerto Princesa', 'luzon', 9.7421, 118.7567, 24.0, 67.8),
    ('roxas', 'RPVR', 'Roxas', 'visayas', 11.5977, 122.752, 58.7, 56.8),
    ('sanjosemindoro', 'RPUH', 'San Jose (Mindoro)', 'luzon', 12.3615, 121.047, 43.9, 52.3),
    ('sanvicente', 'RPSV', 'San Vicente', 'luzon', 10.525, 119.274, 28.5, 63.2),
    ('siargao', 'RPNS', 'Siargao', 'mindanao', 9.8591, 126.014, 87.1, 67.1),
    ('surigao', 'RPMS', 'Surigao', 'mindanao', 9.7558, 125.481, 82.4, 67.7),
    ('tacloban', 'RPVA', 'Tacloban', 'visayas', 11.2276, 125.0278, 78.5, 59.0),
    ('tawitawi', 'RPMN', 'Tawi-Tawi', 'mindanao', 5.047, 119.743, 32.5, 95.6),
    ('tuguegarao', 'RPUT', 'Tuguegarao', 'luzon', 17.6434, 121.733, 49.9, 21.0),
    ('virac', 'RPUV', 'Virac', 'luzon', 13.5764, 124.206, 71.4, 45.1),
    ('zamboanga', 'RPMZ', 'Zamboanga', 'mindanao', 6.922, 122.0622, 52.7, 84.5),
]

# Map projection (longitude -> x %, latitude -> y %) for placing earthquakes on the map image.
P = {"cx": [8.69278161, -1008.33883896], "cy": [-5.91775171, 125.45788502]}

# =====================================================================================
# SOURCES AND FALLBACK ORDER
# For each kind of data the script tries the sources below from left to right and uses
# the first one that answers with usable data. Change the order here to change priority.
# =====================================================================================
SOURCE_ORDER = {
    'reports':   ['aviationweather', 'noaa'],        # official airport weather reports (METAR)
    'forecasts': ['aviationweather', 'noaa'],        # official airport forecasts (TAF)
    'estimates': ['metno', 'openmeteo'],             # computer forecast where no official report exists
    'storms':    ['sigmet', 'gdacs'],                # tropical cyclones (typhoons)
    'quakes':    ['phivolcs', 'usgs', 'emsc'],       # earthquakes
}
SOURCE_NAMES = {
    'aviationweather': 'aviationweather.gov (US Aviation Weather Center)',
    'noaa':            'NOAA data server (tgftp.nws.noaa.gov)',
    'metno':           'MET Norway (api.met.no)',
    'openmeteo':       'Open-Meteo (api.open-meteo.com)',
    'sigmet':          'Aviation storm warnings (aviationweather.gov)',
    'gdacs':           'GDACS, UN and EU disaster alert system (gdacs.org)',
    'phivolcs':        'PHIVOLCS (earthquake.phivolcs.dost.gov.ph)',
    'usgs':            'USGS (earthquake.usgs.gov)',
    'emsc':            'EMSC (seismicportal.eu)',
}
SHORT = {'aviationweather': 'aviationweather.gov', 'noaa': 'NOAA data server', 'metno': 'MET Norway', 'openmeteo': 'Open-Meteo',
         'sigmet': 'aviationweather.gov', 'gdacs': 'GDACS', 'phivolcs': 'PHIVOLCS', 'usgs': 'USGS', 'emsc': 'EMSC'}
GROUP_LABEL = {'reports': 'Airport weather reports', 'forecasts': 'Airport forecasts', 'estimates': 'Estimates (no official report)',
               'storms': 'Typhoon watch', 'quakes': 'Earthquakes'}
STATUS = {g: [] for g in SOURCE_ORDER}      # filled in as sources are tried: (key, 'used' | 'failed' | 'standby', note)
USED = {g: None for g in SOURCE_ORDER}

def fetch(url, tries=2, text=False, insecure_ok=False, timeout=40):
    """Download a URL. Returns parsed JSON (or text), or None if it could not be reached."""
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*'})
            try:
                r = urllib.request.urlopen(req, timeout=timeout)
            except Exception as e:
                # Some government sites publish an incomplete security certificate chain.
                # Only for sources flagged insecure_ok do we retry without certificate checking.
                if insecure_ok and 'CERTIFICATE' in str(e).upper():
                    r = urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())
                else:
                    raise
            with r:
                body = r.read().decode('utf-8', 'replace')
            if text: return body
            return json.loads(body) if body.strip() else []
        except Exception as e:
            last = e; time.sleep(1 + 2 * k)
    print('FETCH FAILED', url[:100], last, file=sys.stderr)
    return None

IDS = ','.join(a[1] for a in APTS)
NOW = dt.datetime.now(dt.timezone.utc)
PROBLEMS = []
BBOX = dict(minlat=3, maxlat=22, minlon=114, maxlon=130)     # "Philippine area" for earthquakes
