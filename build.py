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
import json, re, math, os, sys, time, html, datetime as dt
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
    'storms':    ['sigmet', 'jma', 'gdacs'],         # tropical cyclones (typhoons). All three are read at every check and compared
    'quakes':    ['phivolcs', 'usgs', 'emsc'],       # earthquakes
}
SOURCE_NAMES = {
    'aviationweather': 'aviationweather.gov (US Aviation Weather Center)',
    'noaa':            'NOAA data server (tgftp.nws.noaa.gov)',
    'metno':           'MET Norway (api.met.no)',
    'openmeteo':       'Open-Meteo (api.open-meteo.com)',
    'sigmet':          'Aviation storm warnings (aviationweather.gov)',
    'gdacs':           'GDACS, UN and EU disaster alert system (gdacs.org)',
    'jma':             'RSMC Tokyo typhoon advisories, Japan Meteorological Agency (via the NOAA data server)',
    'phivolcs':        'PHIVOLCS (earthquake.phivolcs.dost.gov.ph)',
    'usgs':            'USGS (earthquake.usgs.gov)',
    'emsc':            'EMSC (seismicportal.eu)',
}
SHORT = {'aviationweather': 'aviationweather.gov', 'noaa': 'NOAA data server', 'metno': 'MET Norway', 'openmeteo': 'Open-Meteo',
         'sigmet': 'aviationweather.gov', 'gdacs': 'GDACS', 'jma': 'RSMC Tokyo', 'phivolcs': 'PHIVOLCS', 'usgs': 'USGS', 'emsc': 'EMSC'}
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
_start = (NOW - dt.timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S')

# ---------- official airport reports and forecasts ----------
_WIND = re.compile(r'\b(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?KT\b')
_WX = re.compile(r'^(\+|-|VC)?(MI|PR|BC|DR|BL|SH|TS|FZ)*(DZ|RA|SN|SG|PL|GR|GS|BR|FG|FU|VA|DU|SA|HZ|SQ|FC|SS|DS)*$')

def _ddhh(day, hour, ref):
    """Turn a day-of-month and hour from a report into a full UTC time near the reference time."""
    day, hour = int(day), int(hour); add = 0
    if hour == 24: hour = 0; add = 1
    best = None
    for mo in (-1, 0, 1):
        y, m = ref.year, ref.month + mo
        if m < 1: y, m = y - 1, 12
        if m > 12: y, m = y + 1, 1
        try: t = dt.datetime(y, m, day, hour, tzinfo=dt.timezone.utc) + dt.timedelta(days=add)
        except ValueError: continue
        if best is None or abs((t - ref).total_seconds()) < abs((best - ref).total_seconds()): best = t
    return best

def parse_raw_metar(icao, raw, ref):
    raw = ' '.join(raw.split())
    m = re.search(r'\b(\d{2})(\d{2})(\d{2})Z\b', raw)
    if not m: return None
    obs = _ddhh(m.group(1), m.group(2), ref) + dt.timedelta(minutes=int(m.group(3)))
    w = _WIND.search(raw); t = re.search(r'\s(M?\d{2})/(M?\d{2})?(\s|$)', raw)
    if not t: return None
    temp = int(t.group(1).replace('M', '-'))
    return dict(icaoId=icao, obsTime=int(obs.timestamp()), rawOb=raw, wspd=int(w.group(2)) if w else 0,
                wgst=int(w.group(3)) if (w and w.group(3)) else None, temp=temp)

def parse_raw_taf(icao, raw, ref):
    toks = raw.replace('=', ' ').split()
    while toks and toks[0] in ('TAF', 'AMD', 'COR'): toks.pop(0)
    if not toks or toks[0] != icao: return None
    toks.pop(0)
    while toks and toks[0] in ('TAF', 'AMD', 'COR'): toks.pop(0)
    mi = re.match(r'^(\d{2})(\d{2})(\d{2})Z$', toks[0]) if toks else None
    if not mi: return None
    issue = _ddhh(mi.group(1), mi.group(2), ref) + dt.timedelta(minutes=int(mi.group(3))); toks.pop(0)
    mv = re.match(r'^(\d{2})(\d{2})/(\d{2})(\d{2})$', toks[0]) if toks else None
    if not mv: return None
    vfrom = _ddhh(mv.group(1), mv.group(2), issue); vto = _ddhh(mv.group(3), mv.group(4), issue); toks.pop(0)
    groups = [dict(change=None, prob=None, a=vfrom, b=vto, toks=[])]
    i = 0
    while i < len(toks):
        t = toks[i]
        fm = re.match(r'^FM(\d{2})(\d{2})(\d{2})$', t)
        if fm:
            a = _ddhh(fm.group(1), fm.group(2), issue) + dt.timedelta(minutes=int(fm.group(3)))
            for g in groups:
                if g['change'] in (None, 'FM') and g['b'] > a: g['b'] = a
            groups.append(dict(change='FM', prob=None, a=a, b=vto, toks=[])); i += 1; continue
        if t in ('TEMPO', 'BECMG') or re.match(r'^PROB\d{2}$', t):
            prob = int(t[4:]) if t.startswith('PROB') else None; change = 'PROB' if prob else t
            if prob and i + 1 < len(toks) and toks[i + 1] == 'TEMPO': change = 'TEMPO'; i += 1
            p = re.match(r'^(\d{2})(\d{2})/(\d{2})(\d{2})$', toks[i + 1]) if i + 1 < len(toks) else None
            if p:
                a = _ddhh(p.group(1), p.group(2), issue); b = _ddhh(p.group(3), p.group(4), issue)
                if change == 'BECMG': b = vto
                groups.append(dict(change=change, prob=prob, a=a, b=b, toks=[])); i += 2; continue
        groups[-1]['toks'].append(t); i += 1
    fc = []
    for g in groups:
        w = None
        for t in g['toks']:
            w = _WIND.match(t) or w
        wx = [t for t in g['toks'] if _WX.match(t) and re.search(r'TS|SH|DZ|RA|FG|GR|SQ|FC|BR|HZ', t)]
        fc.append(dict(timeFrom=int(g['a'].timestamp()), timeTo=int(g['b'].timestamp()), fcstChange=g['change'], probability=g['prob'],
                       wxString=' '.join(wx) or None, wspd=int(w.group(2)) if w else None, wgst=int(w.group(3)) if (w and w.group(3)) else None))
    return dict(icaoId=icao, issueTime=issue.strftime('%Y-%m-%dT%H:%M:%S.000Z'), validTimeFrom=int(vfrom.timestamp()),
                validTimeTo=int(vto.timestamp()), rawTAF=' '.join(raw.split()), fcsts=fc)

def _noaa(kind, only=None):
    """Backup for airport reports/forecasts: the US weather service file server, one small text file per airport."""
    out = []; reached = False
    for a in (APTS if only is None else [x for x in APTS if x[1] in only]):
        sub = 'observations/metar/stations' if kind == 'metar' else 'forecasts/taf/stations'
        body = fetch(f'https://tgftp.nws.noaa.gov/data/{sub}/{a[1]}.TXT', tries=1, text=True, timeout=20)
        if body is None: continue
        reached = True
        try:
            lines = [l for l in body.strip().splitlines() if l.strip()]
            ref = dt.datetime.strptime(lines[0].strip(), '%Y/%m/%d %H:%M').replace(tzinfo=dt.timezone.utc)
            rec = parse_raw_metar(a[1], ' '.join(lines[1:]), ref) if kind == 'metar' else parse_raw_taf(a[1], ' '.join(lines[1:]), ref)
            if rec: out.append(rec)
        except Exception as e:
            print('NOAA PARSE ERROR', a[1], e, file=sys.stderr)
    return out if (reached and out) else None

def load_reports(key):
    if key == 'aviationweather':
        d = fetch(f'https://aviationweather.gov/api/data/metar?ids={IDS}&format=json&hours=3')
        return d if d else None
    if key == 'noaa': return _noaa('metar')
def load_forecasts(key):
    if key == 'aviationweather':
        d = fetch(f'https://aviationweather.gov/api/data/taf?ids={IDS}&format=json')
        return d if d else None
    if key == 'noaa': return _noaa('taf')

# ---------- estimates ----------
def load_metno(wanted):
    out = {}
    for a in wanted:
        m = fetch(f'https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={a[4]:.4f}&lon={a[5]:.4f}', tries=2)
        if m and m.get('properties', {}).get('timeseries'): m['_src'] = 'metno'; out[a[1]] = m
        time.sleep(0.2)
    return out
def openmeteo_to_met(j):
    """Reshape one Open-Meteo answer into the same layout as a MET Norway answer."""
    h = j['hourly']; ts = []
    for i, t in enumerate(h['time']):
        nxt = h['precipitation'][i + 1] if i + 1 < len(h['time']) else None      # Open-Meteo rain is for the hour that just ended
        e = {'time': t + ':00Z', 'data': {'instant': {'details': {'air_temperature': h['temperature_2m'][i],
             'wind_speed': (h['wind_speed_10m'][i] or 0) / 3.6, 'cloud_area_fraction': h['cloud_cover'][i] or 0}}}}
        if nxt is not None: e['data']['next_1_hours'] = {'details': {'precipitation_amount': nxt or 0.0}}
        ts.append(e)
    upd = NOW.replace(minute=0, second=0, microsecond=0)
    return {'properties': {'meta': {'updated_at': upd.strftime('%Y-%m-%dT%H:%M:%SZ')}, 'timeseries': ts}, '_src': 'openmeteo'}
def load_openmeteo(wanted):
    out = {}
    if not wanted: return out
    url = ('https://api.open-meteo.com/v1/forecast?latitude=' + ','.join(f'{a[4]:.4f}' for a in wanted) + '&longitude=' + ','.join(f'{a[5]:.4f}' for a in wanted) +
           '&hourly=temperature_2m,precipitation,wind_speed_10m,cloud_cover&wind_speed_unit=kmh&timezone=UTC&past_hours=2&forecast_days=5')
    d = fetch(url, tries=2)
    if d is None: return out
    if isinstance(d, dict): d = [d]
    for a, j in zip(wanted, d):
        try: out[a[1]] = openmeteo_to_met(j)
        except Exception as e: print('OPEN-METEO PARSE ERROR', a[1], e, file=sys.stderr)
    return out
EST_LOADERS = {'metno': load_metno, 'openmeteo': load_openmeteo}

# ---------- chance of rain ----------
# MET Norway gives the expected amount of rain but no percentage chance for the Philippines.
# Open-Meteo publishes an hourly chance of rain, so it is read here for the hour-by-hour strip only.
# It never affects alert levels. If it cannot be reached, the strip simply shows no percentage.
def load_rain_chance():
    out = {}
    url = ('https://api.open-meteo.com/v1/forecast?latitude=' + ','.join(f'{a[4]:.4f}' for a in APTS) + '&longitude=' + ','.join(f'{a[5]:.4f}' for a in APTS) +
           '&hourly=precipitation_probability&timezone=UTC&forecast_days=2')
    d = fetch(url, tries=2, timeout=30)
    if d is None: return out
    if isinstance(d, dict): d = [d]
    for a, j in zip(APTS, d):
        try:
            h = j['hourly']
            out[a[1]] = {t[:13]: p for t, p in zip(h['time'], h['precipitation_probability']) if p is not None}
        except Exception as e:
            print('RAIN CHANCE PARSE ERROR', a[1], e, file=sys.stderr)
    return out
try: RAIN_CHANCE = load_rain_chance()
except Exception as _e:
    print('RAIN CHANCE ERROR', _e, file=sys.stderr); RAIN_CHANCE = {}

# ---------- 7-day outlook ----------
# A week-ahead view per airport from Open-Meteo: chance of rain, a day and a night picture
# (including thunderstorms), and the high and low temperature. It is a computer forecast for
# planning only and never affects alert levels. If it cannot be reached, the panel is left out.
_HEAVY = (65, 67, 82, 96, 99); _MOD = (63, 66, 81, 95); _LIGHT = (51, 53, 55, 56, 57, 61, 80); _CLOUD = (3, 45, 48); _PART = (1, 2)
def wmo_rank(code):
    """International weather code -> (thunderstorm?, how wet/cloudy 0-5)."""
    c = int(code)
    return (c >= 95, 5 if c in _HEAVY else 4 if c in _MOD else 3 if c in _LIGHT else 2 if c in _CLOUD else 1 if c in _PART else 0)
def wmo_pic(codes, night):
    """Picture code for a group of hours: the most significant weather in the group."""
    codes = [c for c in codes if c is not None]
    if not codes: return ''
    th, wet = max(wmo_rank(c) for c in codes)
    return 'cpolrh'[wet] + ('n' if night else 'd') + ('t' if th else '')
def load_week():
    out = {}
    url = ('https://api.open-meteo.com/v1/forecast?latitude=' + ','.join(f'{a[4]:.4f}' for a in APTS) + '&longitude=' + ','.join(f'{a[5]:.4f}' for a in APTS) +
           '&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum&hourly=weather_code&timezone=Asia%2FManila&forecast_days=8')
    d = fetch(url, tries=2, timeout=40)
    if d is None: return out
    if isinstance(d, dict): d = [d]
    for a, j in zip(APTS, d):
        try:
            dy = j['daily']; hr = dict(zip(j['hourly']['time'], j['hourly']['weather_code']))
            days = []
            for i, day_ in enumerate(dy['time'][:7]):
                nxt = (dt.date.fromisoformat(day_) + dt.timedelta(days=1)).isoformat()
                dcodes = [hr.get(f'{day_}T{h:02d}:00') for h in range(6, 18)]
                ncodes = [hr.get(f'{day_}T{h:02d}:00') for h in range(18, 24)] + [hr.get(f'{nxt}T{h:02d}:00') for h in range(0, 6)]
                tmax, tmin, pp, mm = dy['temperature_2m_max'][i], dy['temperature_2m_min'][i], dy['precipitation_probability_max'][i], dy['precipitation_sum'][i]
                if tmax is None or tmin is None: continue
                days.append([day_, (None if pp is None else int(round(pp))), wmo_pic(dcodes, False) or wmo_pic([dy['weather_code'][i]], False), wmo_pic(ncodes, True) or wmo_pic([dy['weather_code'][i]], True),
                             int(math.floor(tmax + 0.5)), int(math.floor(tmin + 0.5)), (None if mm is None else round(mm, 1))])
            if len(days) >= 5: out[a[1]] = days
        except Exception as e:
            print('WEEK PARSE ERROR', a[1], e, file=sys.stderr)
    return out
# The 7-day outlook changes slowly, so it is fetched at most once an hour and reused in between.
# This keeps the number of requests to Open-Meteo low.
WEEK_EVERY_MIN = 60
WEEK = {}; WEEK_MS = 0
try:
    with open(OUT, encoding='utf-8') as _f: _pw = json.load(_f)
    _age = (NOW.timestamp() * 1000 - (_pw.get('week_ms') or 0)) / 60000
    if 0 <= _age < WEEK_EVERY_MIN:
        _by = {a['id']: a.get('week') or [] for a in _pw.get('airports', [])}
        _reuse = {a[1]: _by.get(a[0], []) for a in APTS}
        if sum(1 for v in _reuse.values() if len(v) >= 5) >= len(APTS) - 2:
            WEEK = {k: v for k, v in _reuse.items() if len(v) >= 5}; WEEK_MS = int(_pw['week_ms'])
            print(f'7-day outlook: reused (fetched {_age:.0f} minutes ago).')
except Exception:
    pass
if not WEEK:
    try: WEEK = load_week()
    except Exception as _e:
        print('WEEK ERROR', _e, file=sys.stderr); WEEK = {}
    if WEEK: WEEK_MS = int(NOW.timestamp() * 1000)

# ---------- earthquakes: every source is reshaped into the same layout ----------
def _feat(t, lat, lon, depth, mag, place, tsunami=None, felt=None, types=''):
    return {'properties': {'mag': mag, 'place': place, 'time': int(t.timestamp() * 1000), 'tsunami': tsunami, 'felt': felt, 'types': types},
            'geometry': {'coordinates': [lon, lat, depth]}}
QUAKE_ALL = []          # every event from the earthquake source, any size: (time, lat, lon, depth, magnitude, place)
def _inbox(lat, lon): return BBOX['minlat'] <= lat <= BBOX['maxlat'] and BBOX['minlon'] <= lon <= BBOX['maxlon']
_C16 = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
def _phiv_place(s):
    """'051 km S 71° W of Palimbang (Sultan Kudarat)' -> '51 km WSW of Palimbang (Sultan Kudarat)'"""
    s = ' '.join(s.split())
    m = re.match(r'^(\d+)\s*km\s+([NS])\s*(\d{1,2})\s*°?\s*([EW])\s+of\s+(.+)$', s)
    if m:
        ang = int(m.group(3)); b = {('N', 'E'): ang, ('N', 'W'): 360 - ang, ('S', 'E'): 180 - ang, ('S', 'W'): 180 + ang}[(m.group(2), m.group(4))]
        return f"{int(m.group(1))} km {_C16[int((b % 360 + 11.25) // 22.5) % 16]} of {m.group(5)}"
    m = re.match(r'^(\d+)\s*km\s+(North|South|East|West)\s+of\s+(.+)$', s)
    if m: return f"{int(m.group(1))} km {m.group(2)[0]} of {m.group(3)}"
    return s
def parse_phivolcs(html):
    """Read the earthquake table on the PHIVOLCS page. Returns (all rows found, rows that pass our filters)."""
    txt = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', html, flags=re.S | re.I)
    txt = re.sub(r'<[^>]+>', ' ', txt); txt = txt.replace('&nbsp;', ' ').replace('&deg;', '°').replace('&#176;', '°')
    txt = re.sub(r'&[a-z#0-9]+;', ' ', txt); txt = ' '.join(txt.split())
    pat = re.compile(r'(\d{1,2}) ([A-Z][a-z]+) (\d{4}) - (\d{1,2}):(\d{2}) ([AP]M) (\d{1,2}\.\d+) (\d{2,3}\.\d+) (\d{1,3}) (\d\.\d) (.*?)(?= \d{1,2} [A-Z][a-z]+ \d{4} - \d{1,2}:\d{2} [AP]M |$)')
    rows = []; pht = dt.timezone(dt.timedelta(hours=8))
    for m in pat.finditer(txt):
        try:
            hh = int(m.group(4)) % 12 + (12 if m.group(6) == 'PM' else 0)
            t = dt.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", '%d %B %Y').replace(hour=hh, minute=int(m.group(5)), tzinfo=pht)
            place = m.group(11).strip()
            if ')' in place: place = place[:place.rindex(')') + 1]       # drop any page text after the last row
            if len(place) > 120: place = place[:120].rsplit(' ', 1)[0]
            rows.append((t.astimezone(dt.timezone.utc), float(m.group(7)), float(m.group(8)), int(m.group(9)), float(m.group(10)), _phiv_place(place)))
        except Exception: continue
    return rows
def load_quakes(key):
    since = NOW - dt.timedelta(days=7)
    if key == 'phivolcs':
        html = fetch('https://earthquake.phivolcs.dost.gov.ph/', tries=2, text=True, insecure_ok=True, timeout=60)
        if not html: return None
        rows = parse_phivolcs(html)
        # Safety check: the page normally lists hundreds of events, the newest only hours old. Otherwise do not trust the reading.
        if len(rows) < 30 or max(r[0] for r in rows) < NOW - dt.timedelta(hours=36) or min(r[0] for r in rows) > since + dt.timedelta(days=1):
            print('PHIVOLCS page did not pass the safety check; rows read:', len(rows), file=sys.stderr); return None
        QUAKE_ALL[:] = [r for r in rows if since <= r[0] <= NOW + dt.timedelta(minutes=10) and _inbox(r[1], r[2])]
        feats = [_feat(t, la, lo, dep, mag, pl) for (t, la, lo, dep, mag, pl) in rows if mag >= 4.5 and since <= t <= NOW + dt.timedelta(minutes=10) and _inbox(la, lo)]
        return {'features': feats, 'metadata': {'generated': int(NOW.timestamp() * 1000)}}
    if key == 'usgs':
        d = fetch('https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=' + _start +
                  f"&minmagnitude=4.5&minlatitude={BBOX['minlat']}&maxlatitude={BBOX['maxlat']}&minlongitude={BBOX['minlon']}&maxlongitude={BBOX['maxlon']}")
        if not isinstance(d, dict) or 'features' not in d: return None
        for f in d['features']: f['properties']['tsunami'] = bool(f['properties'].get('tsunami'))
        return d
    if key == 'emsc':
        d = fetch('https://www.seismicportal.eu/fdsnws/event/1/query?format=json&limit=300&start=' + _start +
                  f"&minmag=4.5&minlat={BBOX['minlat']}&maxlat={BBOX['maxlat']}&minlon={BBOX['minlon']}&maxlon={BBOX['maxlon']}")
        if not isinstance(d, dict) or 'features' not in d: return None
        feats = []
        for f in d['features']:
            p = f['properties']
            try:
                t = dt.datetime.fromisoformat(p['time'].replace('Z', '+00:00'))
                if t.tzinfo is None: t = t.replace(tzinfo=dt.timezone.utc)
                feats.append(_feat(t, float(p['lat']), float(p['lon']), abs(float(p.get('depth') or 0)), float(p['mag']), (p.get('flynn_region') or 'Philippine area').title()))
            except Exception: continue
        return {'features': feats, 'metadata': {'generated': int(NOW.timestamp() * 1000)}}

# ---------- tropical cyclones ----------
def load_storms(key):
    if key == 'sigmet':
        d = fetch('https://aviationweather.gov/api/data/isigmet?format=json')
        return {'sigmet': d} if isinstance(d, list) and d else None
    if key == 'jma':
        j = load_jma_tc()
        return {'jma': j} if j is not None else None
    if key == 'gdacs':
        found = {}; reached = False
        a = (NOW - dt.timedelta(days=4)).strftime('%Y-%m-%d'); b = (NOW + dt.timedelta(days=1)).strftime('%Y-%m-%d')
        for level in ('Green', 'Orange', 'Red'):
            d = fetch(f'https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist=TC&fromdate={a}&todate={b}&alertlevel={level}', tries=1)
            if not isinstance(d, dict): continue
            reached = True
            for f in d.get('features', []):
                p = f.get('properties', {})
                try:
                    if p.get('eventtype') != 'TC': continue
                    td = dt.datetime.fromisoformat(p['todate']).replace(tzinfo=dt.timezone.utc)
                    if str(p.get('iscurrent')).lower() != 'true' and td < NOW - dt.timedelta(hours=18): continue
                    lon, lat = f['geometry']['coordinates'][:2]
                    name = re.sub(r'-\d{2}$', '', p.get('eventname') or p.get('name') or 'Unnamed')
                    sv = p.get('severitydata') or {}
                    try: wind = float(sv.get('severity')) if 'km' in str(sv.get('severityunit', 'km/h')).lower() else None
                    except Exception: wind = None
                    found[p.get('eventid')] = dict(name='-'.join(w.capitalize() for w in name.split('-')), la=float(lat), lo=float(lon), wind=wind)
                except Exception: continue
        return {'gdacs': list(found.values())} if reached else None

JMA_HOURS = 12        # an RSMC Tokyo advisory older than this is ignored (they are issued every 3 to 6 hours)
def load_jma_tc():
    """Tropical cyclone advisories from RSMC Tokyo (Japan Meteorological Agency), the World Meteorological Organization's official
    typhoon centre for the western Pacific. They give the strength (maximum winds, measured the same way PAGASA does), how far
    the strong winds reach, and the forecast position. Read from the NOAA data server. Returns a list, or None if not reached.
    Prints lines starting with TYPHOON: so a run log shows what was found."""
    out = []; reached = 0
    _dirw = {'N': 'north', 'NNE': 'north-northeast', 'NE': 'northeast', 'ENE': 'east-northeast', 'E': 'east', 'ESE': 'east-southeast', 'SE': 'southeast', 'SSE': 'south-southeast', 'S': 'south', 'SSW': 'south-southwest', 'SW': 'southwest', 'WSW': 'west-southwest', 'W': 'west', 'WNW': 'west-northwest', 'NW': 'northwest', 'NNW': 'north-northwest'}
    for n in range(20, 26):
        txt = fetch(f'https://tgftp.nws.noaa.gov/data/raw/wt/wtpq{n}.rjtd..txt', tries=1, text=True, timeout=20)
        if not txt: continue
        reached += 1
        try:
            h = re.search(r'WTPQ\d\d RJTD (\d{2})(\d{2})(\d{2})', txt); nm = re.search(r'NAME[ \t]+([A-Z]{2,3})\b(?:[ \t]+(\d{4}))?(?:[ \t]+([A-Z][A-Z-]*))?', txt)
            if not h or not nm: continue
            t = NOW.replace(day=1, hour=int(h.group(2)), minute=int(h.group(3)), second=0, microsecond=0) + dt.timedelta(days=int(h.group(1)) - 1)
            if t > NOW + dt.timedelta(hours=2): t = (t.replace(day=1) - dt.timedelta(days=1)).replace(day=1) + dt.timedelta(days=int(h.group(1)) - 1)     # issued last month
            if not (-2 <= (NOW - t).total_seconds() / 3600 <= JMA_HOURS): continue
            ana, _, fcst = txt.partition('FORECAST')
            ps = re.search(r'PSTN\s+\d{6}UTC\s+(\d+\.\d)([NS])\s+(\d+\.\d)([EW])', ana)
            if not ps: continue
            la = float(ps.group(1)) * (1 if ps.group(2) == 'N' else -1); lo = float(ps.group(3)) * (1 if ps.group(4) == 'E' else -1)
            num = lambda pat, src: (int(re.search(pat, src).group(1)) if re.search(pat, src) else None)
            def reach(tag):         # the furthest the winds of this strength extend, in km
                m = re.search(tag + r'\s+(.*)', ana); v = [int(x) for x in re.findall(r'(\d+)NM', m.group(1))] if m else []
                return round(max(v) * 1.852) if v else None
            mv = re.search(r'MOVE\s+([A-Z]{1,3})\s+(\d+)KT', ana); f24 = re.search(r'24HF\s+\d{6}UTC\s+(\d+\.\d)([NS])\s+(\d+\.\d)([EW])', fcst)
            f24w = num(r'24HF[^\n]*\n(?:[^\n]*\n){0,3}?MXWD\s+(\d+)KT', fcst)
            kt = num(r'MXWD\s+(\d+)KT', ana); gust = num(r'GUST\s+(\d+)KT', ana)
            name = ('-'.join(w.capitalize() for w in nm.group(3).split('-')) if nm.group(3) else '')
            out.append(dict(name=name, cls=nm.group(1), la=la, lo=lo, issued=t, wind=(round(kt * 1.852) if kt else None), gust=(round(gust * 1.852) if gust else None),
                            gale=reach('30KT'), storm=reach('50KT'), mv=(_dirw.get(mv.group(1)) if mv else None), sp=(round(int(mv.group(2)) * 1.852) if mv else None),
                            still=bool(re.search(r'MOVE\s+(ALMOST STATIONARY|STNR)', ana)), wind24=(round(f24w * 1.852) if f24w else None),
                            fc=((float(f24.group(1)) * (1 if f24.group(2) == 'N' else -1), float(f24.group(3)) * (1 if f24.group(4) == 'E' else -1)) if f24 else None)))
            print(f"TYPHOON: RSMC Tokyo advisory wtpq{n}: {nm.group(1)} {name or '(no name)'} at {la:.1f}N {lo:.1f}E, winds {kt} kt, 30 kt reach {out[-1]['gale']} km, issued {t.strftime('%d %b %H:%MZ')}", file=sys.stderr)
        except Exception as e:
            print(f'TYPHOON: RSMC Tokyo advisory wtpq{n} not understood: {e}', file=sys.stderr)
    if not reached: print('TYPHOON: RSMC Tokyo advisories not reached.', file=sys.stderr); return None
    return out

def run_chain(group, loader):
    """Try each source for this kind of data in priority order; keep the first that works."""
    result = None
    for key in SOURCE_ORDER[group]:
        if result is not None: STATUS[group].append((key, 'standby', 'Backup, not needed this time')); continue
        try: r = loader(key)
        except Exception as e:
            print('SOURCE ERROR', group, key, e, file=sys.stderr); r = None
        if r is None: STATUS[group].append((key, 'failed', 'Could not be reached or read'))
        else: result = r; USED[group] = key; STATUS[group].append((key, 'used', 'Used'))
    return result

METAR = run_chain('reports', load_reports)
TAF = run_chain('forecasts', load_forecasts)
QUAKES = run_chain('quakes', load_quakes)
_st = run_chain('storms', load_storms) or {}
SIGMET = _st.get('sigmet'); GDACS = _st.get('gdacs'); JMATC = _st.get('jma')
# Typhoons are cross-checked, so every typhoon source is read at every check, not only the first one that answers.
for _k in ('jma', 'gdacs'):
    if _k in _st: continue
    try: _r = load_storms(_k)
    except Exception as _e: print('SOURCE ERROR storms', _k, _e, file=sys.stderr); _r = None
    if _k == 'jma': JMATC = (_r or {}).get('jma') if _r else None
    else: GDACS = (_r or {}).get('gdacs') if _r else None
    STATUS['storms'] = [(k, ('used' if _r is not None else 'failed'), ('Used' if _r is not None else 'Could not be reached or read')) if k == _k else (k, st, note) for (k, st, note) in STATUS['storms']]
if USED['storms'] is None and (JMATC is not None or GDACS is not None): USED['storms'] = 'jma' if JMATC is not None else 'gdacs'
MET = {}
for _k in SOURCE_ORDER['estimates']:
    _want = [a for a in APTS if a[1] not in MET]
    if not _want: STATUS['estimates'].append((_k, 'standby', 'Backup, not needed this time')); continue
    _got = EST_LOADERS[_k](_want); MET.update(_got)
    if _got:
        if USED['estimates'] is None: USED['estimates'] = _k
        STATUS['estimates'].append((_k, 'used', 'Used' if len(_got) == len(APTS) else f'Used for {len(_got)} of {len(APTS)} airports'))
    else: STATUS['estimates'].append((_k, 'failed', 'Could not be reached or read'))

def _names(group): return ' and '.join(SHORT[k] for k in SOURCE_ORDER[group])
if METAR is None: PROBLEMS.append(f"Official airport reports could not be reached ({_names('reports')}), so every airport is shown as an Estimate."); METAR = []
elif USED['reports'] != SOURCE_ORDER['reports'][0]: PROBLEMS.append(f"Airport reports: {SHORT[SOURCE_ORDER['reports'][0]]} could not be reached, so the backup source ({SHORT[USED['reports']]}) is being used.")
if TAF is None: PROBLEMS.append(f"Official airport forecasts could not be reached ({_names('forecasts')})."); TAF = []
elif USED['forecasts'] != SOURCE_ORDER['forecasts'][0]: PROBLEMS.append(f"Airport forecasts: {SHORT[SOURCE_ORDER['forecasts'][0]]} could not be reached, so the backup source ({SHORT[USED['forecasts']]}) is being used.")
if len(MET) < len(APTS): PROBLEMS.append(f"Estimates could not be reached for {len(APTS) - len(MET)} of {len(APTS)} airports ({_names('estimates')}).")
elif any(m['_src'] != SOURCE_ORDER['estimates'][0] for m in MET.values()): PROBLEMS.append(f"Estimates: {SHORT[SOURCE_ORDER['estimates'][0]]} could not be reached for some airports, so the backup source is being used for those.")
if SIGMET is None and GDACS is None and JMATC is None: PROBLEMS.append(f"Typhoon data could not be reached ({_names('storms')}), so the typhoon watch is not available.")
elif USED['storms'] != SOURCE_ORDER['storms'][0]: PROBLEMS.append(f"Typhoon watch: {SHORT[SOURCE_ORDER['storms'][0]]} could not be reached, so the backup source ({SHORT[USED['storms']]}) is being used. It shows where each storm is, but not its movement or area warnings.")
if QUAKES is None: PROBLEMS.append(f"Earthquake data could not be reached ({_names('quakes')}).")
elif USED['quakes'] != SOURCE_ORDER['quakes'][0]: PROBLEMS.append(f"Earthquakes: {SHORT[SOURCE_ORDER['quakes'][0]]} could not be reached, so the backup source ({SHORT[USED['quakes']]}) is being used.")
if not METAR and not MET:
    print('No weather source could be reached. Keeping the previous data.json.', file=sys.stderr); sys.exit(1)
QSRC = SHORT[USED['quakes']] if USED['quakes'] else 'USGS'

PHT=dt.timezone(dt.timedelta(hours=8))
def ph(t): return t.astimezone(PHT)
def clock(t):
    t=ph(t); h=t.hour%12 or 12
    if t.hour==0 and t.minute==0: return '12:00 midnight'
    if t.hour==12 and t.minute==0: return '12:00 noon'
    return f"{h}:{t.minute:02d} {'AM' if t.hour<12 else 'PM'}"
def clock_plain(t):
    t=ph(t); h=t.hour%12 or 12; return f"{h}:{t.minute:02d} {'AM' if t.hour<12 else 'PM'}"
def day(t): t=ph(t); return f"{t.strftime('%b')} {t.day}"
MIDNIGHT=(ph(NOW)+dt.timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0)
SOON=NOW+dt.timedelta(hours=1)
def windword(k): return 'Strong wind' if k>=39 else ('Breezy' if k>=20 else 'Light wind')
TODO={'normal':'No action needed.','advisory':'Bad weather is expected later today. Plan ramp work around it and keep watching for updates.',
      'warning':'As a precaution, be ready to pause ramp work. Stay alert and work carefully.','danger':'Thunderstorm at the airport. Work at the ramp with extra care. Safety is the priority at all times.'}
SRC_OFF='Official airport weather report and forecast (aviationweather.gov).'
SRC_EST='Estimate from the MET Norway forecast for this location. No official airport report is available. Estimates show rain and wind only and cannot confirm thunderstorms.'

# ---------- MET Norway ----------
def met_parse(ic):
    m=MET.get(ic)
    if not m: return None
    upd=dt.datetime.fromisoformat(m['properties']['meta']['updated_at'].replace('Z','+00:00'))
    hrs=[]
    for e in m['properties']['timeseries']:
        t=dt.datetime.fromisoformat(e['time'].replace('Z','+00:00'))
        n1=e['data'].get('next_1_hours')
        if not n1: continue
        d=e['data']['instant']['details']
        hrs.append(dict(t=t,p=n1['details'].get('precipitation_amount',0.0),w=d['wind_speed']*3.6,temp=d['air_temperature'],cloud=d.get('cloud_area_fraction',0)))
    cur=[h for h in hrs if h['t']<=NOW<h['t']+dt.timedelta(hours=1)]
    if not cur: return None
    i0=hrs.index(cur[0]); hrs=hrs[i0:]
    def bad(h): return h['p']>=2.5 or round(h['w'])>=39
    runs=[]; i=0
    while i<len(hrs) and hrs[i]['t']<MIDNIGHT:
        if bad(hrs[i]):
            j=i
            while j+1<len(hrs) and bad(hrs[j+1]) and hrs[j+1]['t']-hrs[j]['t']==dt.timedelta(hours=1): j+=1
            seg=hrs[i:j+1]; pm=max(h['p'] for h in seg); wm=max(round(h['w']) for h in seg)
            kind=('heavy rain' if pm>=7.6 else 'moderate rain') if pm>=2.5 else ''
            if wm>=39: kind=(kind+' and strong winds') if kind else 'strong winds'
            runs.append(dict(start=seg[0]['t'],end=seg[-1]['t']+dt.timedelta(hours=1),kind=kind,now=(i==0)))
            i=j+1
        else: i+=1
    later=sum(h['p'] for h in hrs[1:] if h['t']<MIDNIGHT)
    T0=MIDNIGHT; T1=MIDNIGHT+dt.timedelta(days=1)
    th=[h for h in hrs if T0<=h['t']<T1]; truns=[]; i=0
    while i<len(th):
        if bad(th[i]):
            j=i
            while j+1<len(th) and bad(th[j+1]): j+=1
            seg=th[i:j+1]; pm=max(h['p'] for h in seg); wm=max(round(h['w']) for h in seg)
            kind=('heavy rain' if pm>=7.6 else 'moderate rain') if pm>=2.5 else ''
            if wm>=39: kind=(kind+' and strong winds') if kind else 'strong winds'
            truns.append(dict(start=seg[0]['t'],end=seg[-1]['t']+dt.timedelta(hours=1),kind=kind,now=False,rank=(2.5 if pm>=7.6 else 2 if pm>=2.5 else 1))); i=j+1
        else: i+=1
    tsum=sum(h['p'] for h in th)
    # days ahead (day+2, day+3) from hourly then 6-hourly values
    lasth=hrs[-1]['t']+dt.timedelta(hours=1); days=[]
    for k in (2,3):
        D0=MIDNIGHT+dt.timedelta(days=k-1); D1=D0+dt.timedelta(days=1); tot=0.0; wmax=0; cov=dt.timedelta(0)
        for h in hrs:
            if D0<=h['t']<D1: tot+=h['p']; wmax=max(wmax,round(h['w'])); cov+=dt.timedelta(hours=1)
        for e in m['properties']['timeseries']:
            t=dt.datetime.fromisoformat(e['time'].replace('Z','+00:00')); n6=e['data'].get('next_6_hours')
            if t<lasth or not n6 or 'next_1_hours' in e['data']: continue
            a=max(t,D0); b=min(t+dt.timedelta(hours=6),D1)
            if b>a:
                fr=(b-a)/dt.timedelta(hours=6); tot+=n6['details'].get('precipitation_amount',0.0)*fr; cov+=(b-a)
                wmax=max(wmax,round(e['data']['instant']['details']['wind_speed']*3.6))
        if cov>=dt.timedelta(hours=18): days.append((D0,tot,wmax))
    # hour-by-hour strip for the details panel: [time, temperature, rain mm, wind km/h, picture code]
    def pic(h):
        night=not (6<=ph(h['t']).hour<18)
        sky='h' if h['p']>=7.6 else 'r' if h['p']>=2.5 else 'l' if h['p']>=0.2 else ('c' if h['cloud']<25 else 'p' if h['cloud']<75 else 'o')
        return sky+('n' if night else 'd')
    ch=RAIN_CHANCE.get(ic,{})
    hourly=[[int(h['t'].timestamp()*1000),round(h['temp']),round(h['p'],1),round(h['w']),pic(h),ch.get(h['t'].strftime('%Y-%m-%dT%H'))] for h in hrs[:12]]
    return dict(upd=upd,cur=hrs[0],runs=runs,later=later,truns=truns,tsum=tsum,days=days,src=m.get('_src','metno'),hourly=hourly)
def met(ic):
    try: return met_parse(ic)
    except Exception as e:
        print('MET PARSE ERROR',ic,e,file=sys.stderr); return None
def wkday(t): t=ph(t); return f"{t.strftime('%a')}, {t.strftime('%b')} {t.day}"
def days_text(m):
    if not m or not m['days']: return 'No outlook available.'
    out=[]
    for D0,tot,w in m['days']:
        n=int(round(tot)); d='mostly dry' if tot<1 else f'light rain at times (about {n} mm)' if tot<10 else f'rainy periods (about {n} mm)' if tot<30 else f'heavy rain likely (about {n} mm)'
        if w>=39: d+=f', strong winds up to {w} km/h'
        out.append(f"{wkday(D0)}: {d}.")
    return ' '.join(out)+' Estimate from the MET Norway forecast; less certain the further ahead.'
def tspan(a,b):
    T0=MIDNIGHT; T1=MIDNIGHT+dt.timedelta(days=1)
    if a<=T0 and b>=T1: return 'All day'
    return f"{clock(a)} to {clock(b)}"
def est_tmr(m,prefix):
    if m['truns']: return prefix+' '.join((r['kind'][0].upper()+r['kind'][1:] if i else r['kind'])+f" possible {tspan(r['start'],r['end'])}." for i,r in enumerate(m['truns']))
    return prefix+'no moderate or heavy rain expected tomorrow. '+('Light showers possible.' if m['tsum']>=0.5 else 'Mostly dry.')
def pick_tmr(cands):
    if not cands: return dict(t=0,twhat='',twhen='',tsort=0,test=False)
    c=max(cands,key=lambda c:(c['rank'],not c['est'],-c['a'].timestamp()))
    return dict(t=1,twhat=c['what'],twhen=tspan(c['a'],c['b']),tsort=c['a'].timestamp(),test=c['est'])
def est_cands(m): return [dict(a=r['start'],b=r['end'],rank=r['rank'],est=True,what=r['kind'][0].upper()+r['kind'][1:]+' possible') for r in m['truns']]
def span(r,cap=False):
    if r['now']: return ('Now, until ' if cap else 'now until ')+clock(r['end'])
    return f"{clock(r['start'])} to {clock(r['end'])}"
def est_row(m):
    c=m['cur']; p=c['p']; k=round(c['w'])
    cl=c['cloud']; sky='cloudy' if cl>=87.5 else 'mostly cloudy' if cl>=62.5 else 'partly cloudy' if cl>=37.5 else 'mostly clear' if cl>=12.5 else 'clear'
    wx=(sky+', no rain') if p<0.1 else 'light rain' if p<2.5 else 'moderate rain' if p<7.6 else 'heavy rain'
    now=f"Estimate: {wx}, {windword(k).lower()} ({k} km/h), {round(c['temp'])}°C."
    runs=m['runs']
    if runs:
        parts=[f"{r['kind']} possible {span(r)}." for r in runs]
        nxt='Estimate: '+' '.join([parts[0]]+[x[0].upper()+x[1:] for x in parts[1:]])
        r=runs[0]; level='warning' if r['start']<=SOON else 'advisory'
        what=r['kind'][0].upper()+r['kind'][1:]+' possible'; when=span(r,True); sort=0 if r['now'] else r['start'].timestamp()
    else:
        nxt='Estimate: no moderate or heavy rain expected for the rest of today. '+('Light showers possible.' if m['later']>=0.5 else 'Mostly dry.')
        level='normal'; what=when=''; sort=0
    u=m['upd']; upd=f"Estimate updated {clock_plain(u)}." if ph(u).date()==ph(NOW).date() else f"Estimate updated {day(u)}, {clock_plain(u)}."
    r=dict(level=level,now=now,next=nxt,todo=TODO[level],upd=upd,src=SRC_EST,est=True,what=what,when=when,sort=sort,tmr=est_tmr(m,'Estimate: '),days=days_text(m))
    age=(NOW-m['upd']).total_seconds()/3600
    r['conf']=('Lower' if age<=3 else 'Low')+f": there is no official airport report here, so this is a computer forecast (MET Norway) for the location, updated {clock_plain(m['upd'])}. It shows rain and wind only and cannot confirm thunderstorms."
    r.update(pick_tmr(est_cands(m))); return r
def est_name(m): return SHORT[m.get('src','metno')] if m else 'MET Norway'
def rename_est(r,m):
    nm=est_name(m)
    if nm!='MET Norway':
        for k,v in list(r.items()):
            if isinstance(v,str): r[k]=v.replace('MET Norway',nm)
    r['estsrc']=nm if m else ''
    r['hours']=m['hourly'] if m else []
    return r

# ---------- official ----------
def latest_metar(ic):
    xs=[x for x in METAR if x['icaoId']==ic]
    if not xs: return None
    x=max(xs,key=lambda x:x['obsTime'])
    return x if NOW.timestamp()-x['obsTime']<=2.5*3600 else None
def latest_taf(ic):
    xs=[x for x in TAF if x['icaoId']==ic and x.get('validTimeTo',0)>NOW.timestamp()]
    return max(xs,key=lambda x:x['issueTime']) if xs else None
WXRE=re.compile(r'^(\+|-|VC|RE)?(MI|PR|BC|DR|BL|SH|TS|FZ)*(DZ|RA|SN|SG|PL|GR|GS|BR|FG|FU|VA|DU|SA|HZ|SQ|FC|SS|DS)*$')
def wx_tokens(raw):
    body=raw.split(' RMK')[0].split()
    return [t for t in body if WXRE.match(t) and re.search(r'TS|SH|DZ|RA|FG|GR|SQ|FC',t) and not re.match(r'^\d|^Q|^A\d',t)]
def kindtext(tok):
    """plain words for one weather group; returns (text, rank, short)"""
    inten='heavy ' if tok.startswith('+') else ('light ' if tok.startswith('-') else '')
    if 'TS' in tok:
        if re.search(r'RA|DZ|GR',tok): return ('Thunderstorm with '+inten+'rain',3,'Thunderstorm')
        return ('Thunderstorm',3,'Thunderstorm')
    if 'SH' in tok: return (('Heavy rain showers' if tok.startswith('+') else ('Light rain showers' if tok.startswith('-') else 'Rain showers')),2,'Rain showers' if not tok.startswith('+') else 'Heavy rain showers')
    if re.search(r'RA|DZ',tok): 
        t={'heavy ':'Heavy rain','light ':'Light rain','':'Rain'}[inten]; return (t,2,t)
    return (None,0,None)
def off_row(mt,tf,m):
    raw=mt['rawOb']; toks=wx_tokens(raw)
    here=[t for t in toks if not t.startswith(('VC','RE'))]; vc=[t for t in toks if t.startswith('VC')]; rec=[t for t in toks if t.startswith('RE')]
    ts_here=any('TS' in t for t in here)
    precip=[t for t in here if re.search(r'RA|DZ|SH|GR',t)]
    s=[]
    if ts_here:
        p=[t for t in here if 'TS' in t][0]
        allp=''.join(here)
        if re.search(r'RA|DZ|GR',allp):
            s.append('Thunderstorm with '+('heavy rain' if any(t.startswith('+') for t in here) else 'light rain' if all(t.startswith('-') for t in precip) else 'rain')+' at the airport.')
        else: s.append('Thunderstorm at the airport.')
    elif precip:
        t=precip[0]; inten='Heavy ' if t.startswith('+') else 'Light ' if t.startswith('-') else ''
        w='rain showers' if 'SH' in t else 'rain'
        s.append((inten+w).capitalize()+' at the airport.')
    elif any('TS' in t for t in vc): s.append('Thunderstorm near the airport, none at the airport.')
    elif vc: s.append('Rain showers nearby, none at the airport.')
    else: s.append('No rain or thunderstorm at the airport.')
    if any('FG' in t for t in here): s.append('Fog at the airport.')
    if not ts_here:
        if any('TS' in t for t in rec): s.append('Thunderstorm ended within the last hour.')
        elif rec and not precip: s.append('Rain ended within the last hour.')
        if re.search(r'\d{3}(CB|TCU)\b',raw.split(' RMK')[0]): s.append('Storm clouds near the airport.')
    k=round((mt.get('wspd') or 0)*1.852); g=round((mt.get('wgst') or 0)*1.852)
    obs=dt.datetime.fromtimestamp(mt['obsTime'],dt.timezone.utc)
    s.append(f"{windword(max(k,g))} ({k} km/h{', gusts '+str(g)+' km/h' if g else ''}), {round(mt['temp'])}°C, as of {clock_plain(obs)}.")
    now=' '.join(s)
    # forecast periods
    periods=[]
    if tf:
        for f in tf['fcsts']:
            a=dt.datetime.fromtimestamp(f['timeFrom'],dt.timezone.utc); b=dt.datetime.fromtimestamp(f['timeTo'],dt.timezone.utc)
            if b<=NOW or a>=MIDNIGHT: continue
            best=(None,0,None)
            for t in (f.get('wxString') or '').split():
                kt=kindtext(t)
                if kt[1]>best[1] or (kt[1]==best[1] and kt[0] and best[0] and len(kt[0])>len(best[0])): best=kt
            wk=max(round((f.get('wspd') or 0)*1.852),round((f.get('wgst') or 0)*1.852))
            if best[1]==0 and wk>=39: best=('Strong winds',1,'Strong winds')
            if best[1]==0: continue
            cert='possible' if (f.get('fcstChange') in ('TEMPO','PROB') or f.get('probability')) else 'expected'
            long_=(f"possible ({f['probability']}% chance)" if f.get('probability') else 'possible at times') if cert=='possible' else 'expected'
            periods.append(dict(a=a,b=b,text=best[0],rank=best[1],short=best[2],cert=cert,long=long_,now=a<=NOW))
    periods.sort(key=lambda p:p['a'])
    def pspan(p,cap=False):
        if p['now']: return ('Now, until ' if cap else 'now to ')+clock(p['b'])
        return f"{clock(p['a'])} to {clock(p['b'])}"
    nx=[f"{p['text']} {p['long']} {pspan(p)}." for p in periods]
    if not tf: nx=['No airport forecast is available for the rest of today.']
    elif not nx: nx=['No thunderstorm or rain expected for the rest of today.']
    if m and m['runs']: nx.append('Estimate (MET Norway): '+' '.join(f"{r['kind']} possible {span(r)}." for r in m['runs']).replace('. m','. M').replace('. h','. H').replace('. s','. S'))
    strong_now=max(k,g)>=39
    heavy_now=bool(precip) and not all(t.startswith('-') for t in precip)
    if ts_here: level='danger'; what='Thunderstorm at the airport'; when='Now'; sort=0
    else:
        under=[p for p in periods if p['a']<=SOON]
        if heavy_now or strong_now:
            level='warning'; what=('Rain at the airport' if heavy_now else 'Strong winds at the airport'); when='Now'; sort=0
            if under:
                p=max(under,key=lambda p:(p['rank'],-p['a'].timestamp()))
                if p['rank']>=3: what=f"{p['short']} {p['cert']}"; when=pspan(p,True)
        elif under:
            p=max(under,key=lambda p:(p['now'],p['rank'],-p['a'].timestamp())); level='warning'; what=f"{p['short']} {p['cert']}"; when=pspan(p,True); sort=0 if p['now'] else p['a'].timestamp()
        elif periods:
            p=periods[0]; level='advisory'; what=f"{p['short']} {p['cert']}"; when=pspan(p,True); sort=p['a'].timestamp()
        else: level='normal'; what=when=''; sort=0
    T0=MIDNIGHT; T1=MIDNIGHT+dt.timedelta(days=1); tp=[]; cands=[]
    if tf:
        for f in tf['fcsts']:
            if f.get('fcstChange')=='BECMG' and not (f.get('wxString') or '').strip(): continue
            a=max(dt.datetime.fromtimestamp(f['timeFrom'],dt.timezone.utc),T0); b=min(dt.datetime.fromtimestamp(f['timeTo'],dt.timezone.utc),T1)
            if b<=a: continue
            best=(None,0,None)
            for t in (f.get('wxString') or '').split():
                kt=kindtext(t)
                if kt[1]>best[1] or (kt[1]==best[1] and kt[0] and best[0] and len(kt[0])>len(best[0])): best=kt
            wk=max(round((f.get('wspd') or 0)*1.852),round((f.get('wgst') or 0)*1.852))
            if best[1]==0 and wk>=39: best=('Strong winds',1,'Strong winds')
            if best[1]==0: continue
            cert='possible' if (f.get('fcstChange') in ('TEMPO','PROB') or f.get('probability')) else 'expected'
            long_=(f"possible ({f['probability']}% chance)" if f.get('probability') else 'possible at times') if cert=='possible' else 'expected'
            tp.append((a,f"{best[0]} {long_} {tspan(a,b)}.")); cands.append(dict(a=a,b=b,rank=best[1],est=False,what=f"{best[2]} {cert}"))
        tend=dt.datetime.fromtimestamp(tf['validTimeTo'],dt.timezone.utc)
        if tend<=T0: tm='The airport forecast does not reach tomorrow yet.'
        else:
            cov='' if tend>=T1 else f" (covers until {clock(tend)})"
            tm=f"Airport forecast{cov}: "+(' '.join(x[1] for x in sorted(tp)) if tp else 'no thunderstorm or rain expected.')
    else: tm='No airport forecast is available for tomorrow.'
    if m: tm+=' '+est_tmr(m,'Estimate (MET Norway): '); cands+=est_cands(m)
    tmr_pick=pick_tmr(cands)
    agem=(NOW-obs).total_seconds()/60; offbad=bool(periods) or ts_here or bool(precip); estbad=bool(m and m['runs'])
    conf=('High' if agem<=90 else 'Medium')+f": official airport report from {clock_plain(obs)}"+(' and official airport forecast' if tf else ', but no airport forecast')+'. These rank above any estimate.'
    if agem>90: conf+=' The report is more than 90 minutes old.'
    if m: conf+=(' The MET Norway estimate agrees.' if offbad==estbad else (' The MET Norway estimate shows less rain than the airport forecast; the airport forecast is used.' if offbad else ' The MET Norway estimate shows more rain than the airport forecast; it is noted under Rest of today.'))
    upd=f"Airport report {clock_plain(obs)}."+(f" Airport forecast issued {clock_plain(dt.datetime.fromisoformat(tf['issueTime'].replace('Z','+00:00')))}." if tf else '')
    return dict(level=level,now=now,next=' '.join(nx),todo=TODO[level],upd=upd,src=SRC_OFF,est=False,what=what,when=when,sort=sort,tmr=tm,days=days_text(m),conf=conf,**tmr_pick,_obs=obs,_taf=(dt.datetime.fromisoformat(tf['issueTime'].replace('Z','+00:00')) if tf else None))

rows=[]; obs_times=[]; taf_times=[]; est_times=[]; TS_AIRPORTS=[]; TS_AREAS=[]
for i,ic,nm_,rg_,la,lo,x_,y_ in APTS:
    m=met(ic); mt=latest_metar(ic); tf=latest_taf(ic)
    if m: est_times.append(m['upd'])
    r=None
    if mt:
        try: r=off_row(mt,tf,m); obs_times.append(r.pop('_obs')); t=r.pop('_taf'); t and taf_times.append(t)
        except Exception as e: print('REPORT PARSE ERROR',ic,e,file=sys.stderr); r=None
    if r is None and m: r=est_row(m)
    if r is not None: pass
    else: r=dict(level='nodata',now='No weather data could be reached for this airport.',next='No data.',todo='Check local conditions directly.',upd='No update available.',src='No source reachable.',est=False,what='',when='',sort=0,tmr='No data.',days='No data.',conf='None: no source could be reached for this airport.',t=0,twhat='',twhen='',tsort=0,test=False)
    rename_est(r,m)
    r['week']=WEEK.get(ic,[])
    if not r['est'] and r['level']!='nodata':
        if r['level']=='danger': TS_AIRPORTS.append(dict(id=i,a=int(NOW.timestamp()*1000),b=int((NOW+dt.timedelta(hours=1)).timestamp()*1000)))
        for f in (tf['fcsts'] if tf else []):
            if 'TS' in (f.get('wxString') or '') and f['timeTo']>NOW.timestamp(): TS_AIRPORTS.append(dict(id=i,a=int(f['timeFrom'])*1000,b=int(f['timeTo'])*1000))
    if not r['est'] and r['level']!='nodata': r['src']=f"Official airport weather report ({SHORT[USED['reports']]})"+(f" and forecast ({SHORT[USED['forecasts']]})." if tf else '.')
    r.update(id=i,name=nm_,region=rg_,x=x_,y=y_,icao=ic,lat=la,lon=lo); rows.append(r)

# ---------- earthquakes ----------
def hav(a,b,c,d):
    R=6371; p1,p2=math.radians(a),math.radians(c); x=math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(math.radians(d-b)/2)**2
    return 2*R*math.asin(math.sqrt(x))
quakes=[]; flags=[]; qok=True
# ---------- earthquake alerts ----------
# STRONG_MAG   : an earthquake this strong in the Philippine area in the last 24 hours raises an alert.
# TSUNAMI_MAG  : this strong AND no deeper than TSUNAMI_DEPTH km raises a "possible tsunami" alert,
#                as does any earthquake the USGS marks with its tsunami flag.
# These are prompts to check official PHIVOLCS bulletins. They are not tsunami warnings.
STRONG_MAG = 6.0; TSUNAMI_MAG = 6.5; TSUNAMI_DEPTH = 70
EQ_ALERTS = []
# ---------- aftershocks ----------
# Smaller earthquakes that follow a main earthquake in the same place are grouped with it: each one is a
# small dot on the map, and the main earthquake's details list them. An event counts as an aftershock when
# it is below AFTER_MAX_MAG, within AFTER_KM of a main earthquake of MAIN_MAG or stronger, and no more than
# AFTER_HOURS after it. Stronger aftershocks keep their own ring and their own alert checks.
MAIN_MAG = 5.0; AFTER_MAX_MAG = 5.0; AFTER_KM = 100; AFTER_HOURS = 72
# ---------- second agency ----------
# For earthquakes of CHECK_MAG or stronger in the last 24 hours, a second agency (USGS) is read as well, so the
# dashboard can show both magnitudes. If the second agency places the earthquake within 100 km of an airport,
# that airport is flagged too: the more cautious of the two positions is used.
CHECK_MAG = 5.0
def second_agency():
    """Other earthquake agencies to check the main one against: [(time ms, lat, lon, depth, magnitude, place, agency)].
    Whichever of USGS and EMSC is not already the main source is asked, so there is still a cross-check when PHIVOLCS is down."""
    out = []; main = USED['quakes']
    if main is None: return out
    for key, label in (('usgs', 'USGS'), ('emsc', 'EMSC')):
        if key == main: continue
        try:
            u = load_quakes(key)
            SECOND_OK.append(label) if u is not None else None
            for f in ((u or {}).get('features') or []):
                if f['properties'].get('mag') is None: continue
                out.append((f['properties']['time'], f['geometry']['coordinates'][1], f['geometry']['coordinates'][0], f['geometry']['coordinates'][2] or 0,
                            float(f['properties']['mag']), re.sub(r', Philippines$', '', f['properties'].get('place') or ''), label))
        except Exception as e:
            print('SECOND AGENCY ERROR', key, e, file=sys.stderr)
    return out
SECOND_OK = []
try:
    Q=QUAKES
    if Q is None: raise RuntimeError('no earthquake source reached')
    asof=dt.datetime.fromtimestamp(Q['metadata']['generated']/1000,dt.timezone.utc)
    # group aftershocks under their main earthquake (strongest main first)
    _all = QUAKE_ALL or [(dt.datetime.fromtimestamp(f['properties']['time']/1000,dt.timezone.utc), f['geometry']['coordinates'][1], f['geometry']['coordinates'][0],
                          f['geometry']['coordinates'][2] or 0, f['properties']['mag'], re.sub(r', Philippines$','',f['properties']['place'] or '')) for f in Q['features']]
    _taken = set(); SHOCKS = {}; FOLDED = set()
    for f in sorted(Q['features'], key=lambda f: -f['properties']['mag']):
        pm = f['properties']
        if pm['mag'] < MAIN_MAG: continue
        mlo, mla = f['geometry']['coordinates'][:2]; mt = pm['time']; got = []
        for i, (t_, la_, lo_, dep_, mag_, pl_) in enumerate(_all):
            ms_ = int(t_.timestamp()*1000)
            if i in _taken or mag_ >= AFTER_MAX_MAG or mag_ >= pm['mag'] or not (0 < ms_ - mt <= AFTER_HOURS*3600000): continue
            if hav(mla, mlo, la_, lo_) > AFTER_KM: continue
            _taken.add(i); got.append((ms_, la_, lo_, dep_, mag_, pl_)); FOLDED.add((ms_, round(la_, 2), round(lo_, 2)))
        SHOCKS[mt] = sorted(got, reverse=True)
    _second = second_agency() if any(f['properties']['mag'] >= CHECK_MAG and NOW.timestamp()*1000 - f['properties']['time'] <= 24*3600000 for f in Q['features']) else []
    for f in sorted(Q['features'],key=lambda f:-f['properties']['time']):
        p=f['properties']; lo,la,dep=f['geometry']['coordinates']; t=dt.datetime.fromtimestamp(p['time']/1000,dt.timezone.utc)
        if (p['time'], round(la, 2), round(lo, 2)) in FOLDED: continue        # shown as an aftershock of a main earthquake
        near=min(rows,key=lambda r:hav(la,lo,r['lat'],r['lon'])); dist=hav(la,lo,near['lat'],near['lon'])
        x=P['cx'][0]*lo+P['cx'][1]; y=P['cy'][0]*la+P['cy'][1]; recent=(NOW-t)<=dt.timedelta(hours=24)
        place=re.sub(r', Philippines$','',p['place'])
        dkm=int(round(dist/10)*10); hit=[]
        if recent and p['mag']>=5.0:
            for r in rows:
                dd=hav(la,lo,r['lat'],r['lon'])
                if dd<=100: flags.append((r['name'],p['mag'],round(dd),place,t)); hit.append(r['name'])
        other=None; magnote=''; hit2=[]
        if recent and p['mag']>=CHECK_MAG:
            cands=[s_ for s_ in _second if abs(s_[0]-p['time'])<=3*60000 and hav(la,lo,s_[1],s_[2])<=300]
            if cands:
                other=min(cands,key=lambda s_:abs(s_[0]-p['time']))
                for r in rows:
                    dd=hav(other[1],other[2],r['lat'],r['lon'])
                    if dd<=100 and r['name'] not in hit: flags.append((r['name'],p['mag'],round(dd),other[5]+f', {other[6]} position',t)); hit2.append((r['name'],int(round(dd/10)*10)))
                same=abs(other[4]-p['mag'])<0.15
                magnote=(f"{QSRC}: magnitude {p['mag']:.1f}. {other[6]}{' (United States)' if other[6] == 'USGS' else ' (Europe)'}: magnitude {other[4]:.1f}, {other[5]}, about {max(0,round(other[3]))} km deep. "+
                    ('The two agencies agree. ' if same else 'Agencies use different instruments and methods, so their figures differ. ')+
                    f"Phone alerts and first reports are quick estimates and are often revised. This dashboard shows the {QSRC} figure and follows any revision at its next update.")
            else:
                magnote=f"{QSRC}: magnitude {p['mag']:.1f}. "+('PHIVOLCS, the official Philippine agency, could not be reached at this check and may report a different figure.' if USED['quakes']!='phivolcs' else 'No second agency figure yet.')+f"  Phone alerts and first reports are quick estimates and are often revised; this dashboard follows any {QSRC} revision at its next update."
        hit=hit+[n for n,_ in hit2]
        _agree=sorted({s_[6] for s_ in cands}) if (recent and p['mag']>=CHECK_MAG and other) else []
        check=''
        if recent and p['mag']>=CHECK_MAG:
            if _agree: check=f"Confirmed: {' and '.join(_agree)} also report{'s' if len(_agree)==1 else ''} this earthquake ({other[6]} gives magnitude {other[4]:.1f})."
            elif SECOND_OK: check=f"Not yet confirmed by a second agency ({' and '.join(SECOND_OK)} checked). Other agencies usually report within 10 to 20 minutes; this is updated at the next check."
            else: check='Could not be cross-checked at this check: no second earthquake agency could be reached.'
        dep=max(0,round(dep or 0)); dword='shallow' if dep<70 else 'mid-depth' if dep<300 else 'very deep'
        qid=f'q{len(quakes)}'; tsu_poss=recent and (p.get('tsunami') is True or (p['mag']>=TSUNAMI_MAG and dep<=TSUNAMI_DEPTH)); strong=recent and p['mag']>=STRONG_MAG
        whenq=f"{day(t)}, {clock_plain(t)}"
        if tsu_poss: EQ_ALERTS.append(dict(kind='tsunami',q=qid,ms=p['time'],text=f"Possible tsunami: magnitude {p['mag']:.1f} earthquake, {place} ({whenq}). Check PHIVOLCS tsunami bulletins now, especially for coastal airports."))
        elif strong: EQ_ALERTS.append(dict(kind='strong',q=qid,ms=p['time'],text=f"Strong earthquake: magnitude {p['mag']:.1f}, {place} ({whenq}). Nearest airport: {near['name']}, about {dkm} km away."+(f" USGS places it nearer, about {hit2[0][1]} km from {hit2[0][0]}. Check runways and facilities at {', '.join(hit)}." if hit2 else (f" Check runways and facilities at {', '.join(hit)}." if hit else ''))))
        elif hit: EQ_ALERTS.append(dict(kind='flag',q=qid,ms=p['time'],text=f"Earthquake near {', '.join(hit)}: magnitude {p['mag']:.1f}, {place} ({whenq}). Check runways and facilities."))
        if hit: todo='Earthquake flag. Check runways, buildings and equipment at '+', '.join(hit)+' before normal work continues.'+(f" ({QSRC} places this earthquake more than 100 km away, but USGS places it about {hit2[0][1]} km from {hit2[0][0]}. The more cautious position is used.)" if hit2 else '')
        elif p['mag']<5.0: todo='No action needed. No airport flag: a flag needs magnitude 5.0 or stronger within 100 km of an airport in the last 24 hours.'
        elif not recent: todo='No action needed. This earthquake is more than 24 hours old and is shown for reference.'
        else: todo='No action needed. No airport is within 100 km of this earthquake.'
        sh=SHOCKS.get(p['time'],[]); shocks=[]; slist=[]
        if sh:
            big=max(sh,key=lambda s_:s_[4]); bt=dt.datetime.fromtimestamp(big[0]/1000,dt.timezone.utc); lt=dt.datetime.fromtimestamp(sh[0][0]/1000,dt.timezone.utc)
            aft=(f"{len(sh)} aftershock{'' if len(sh)==1 else 's'} recorded so far by {QSRC}. Strongest: magnitude {big[4]:.1f} ({day(bt)}, {clock_plain(bt)}). Latest: {day(lt)}, {clock_plain(lt)}. "
                 "Each one is a small purple dot on the map. More can follow in the same area over the next days.")
            for s_ in sh[:80]:
                sx=P['cx'][0]*s_[2]+P['cx'][1]; sy=P['cy'][0]*s_[1]+P['cy'][1]
                if 0<=sx<=100 and 0<=sy<=100: shocks.append([round(sx,2),round(sy,2),s_[4],s_[0]])
            for s_ in sh[:8]:
                st_=dt.datetime.fromtimestamp(s_[0]/1000,dt.timezone.utc); slist.append([f"{day(st_)}, {clock_plain(st_)}",s_[4],s_[5]])
        else:
            aft=('No aftershocks recorded yet. ' if (recent and p['mag']>=MAIN_MAG) else '')+'Smaller earthquakes can follow in the same area over the next days.'
        quakes.append(dict(check=check,hits=sorted(set(hit)),ms=p['time'],lat=la,lon=lo,magnote=magnote,shocks=shocks,slist=slist,nshock=len(sh),id=f'q{len(quakes)}',mag=p['mag'],place=place,x=x,y=y,onmap=(0<=x<=100 and 0<=y<=100),op=('1' if recent else '0.5'),size=round(14+(p['mag']-4.5)*16),
            title=f"Magnitude {p['mag']:.1f} earthquake",where=place+'.',when=f"{day(t)}, {clock_plain(t)} (Philippine time)."+(' Within the last 24 hours.' if recent else ''),
            depth=f"About {dep} km below ground ({dword}).",tsu=('Tsunami possible. This was a strong, shallow earthquake'+(' and USGS has flagged it for tsunami information' if p.get('tsunami') is True else '')+'. Check PHIVOLCS tsunami bulletins now, especially for coastal airports.') if tsu_poss else (f'{QSRC} has linked a tsunami notice to this earthquake. Check official tsunami bulletins for coastal airports.' if p.get('tsunami') else (f'No tsunami notice is linked to this earthquake ({QSRC}).' if p.get('tsunami') is False else f'{QSRC} data does not include tsunami notices. For a strong earthquake at sea, check PHIVOLCS tsunami bulletins.')),after=aft+(' USGS has published an aftershock forecast for this earthquake.' if 'oaf' in (p.get('types') or '') else '')+(f" {p['felt']} {'person' if p['felt']==1 else 'people'} reported feeling it to {QSRC}." if p.get('felt') else ''),near=f"{near['name']}, about {dkm} km away.",todo=todo,src=SOURCE_NAMES[USED['quakes']]+'.',
            line=f"{place}. {day(t)}, {clock_plain(t)}. Nearest airport: {near['name']}, about {dkm} km away."))
except Exception as e:
    qok=False; asof=None; quakes=[]; flags=[]; EQ_ALERTS=[]; print('QUAKE ERROR',e,file=sys.stderr)
    if QUAKES is not None: PROBLEMS.append('Earthquake data could not be read.')
# Cross-check: a large earthquake anywhere in the region that USGS marks with its tsunami flag
# (this also catches strong earthquakes outside the Philippine area, which can still send a tsunami here).
try:
    _u = fetch('https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=' + (NOW - dt.timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S') +
               '&minmagnitude=6.5&minlatitude=-10&maxlatitude=40&minlongitude=95&maxlongitude=160', tries=1, timeout=25)
    for _f in ((_u or {}).get('features') or []):
        _p = _f['properties']
        if not _p.get('tsunami'): continue
        if any(a['kind'] == 'tsunami' and abs(a['ms'] - _p['time']) < 15 * 60000 for a in EQ_ALERTS): continue      # already alerted from the main source
        _t = dt.datetime.fromtimestamp(_p['time'] / 1000, dt.timezone.utc)
        EQ_ALERTS.append(dict(kind='tsunami', q='', ms=_p['time'], text=f"Possible tsunami: magnitude {_p['mag']:.1f} earthquake, {_p.get('place') or 'in the region'} ({day(_t)}, {clock_plain(_t)}). USGS has flagged it for tsunami information. Check PHIVOLCS tsunami bulletins now."))
except Exception as _e:
    print('TSUNAMI CROSS-CHECK ERROR', _e, file=sys.stderr)
EQ_ALERTS.sort(key=lambda a: ({'tsunami': 0, 'strong': 1, 'flag': 2}[a['kind']], -a['ms']))
if flags:
    flag='Earthquake flag: '+'; '.join(f"{n} is about {d} km from a magnitude {m:.1f} earthquake ({pl}, {day(t)}, {clock_plain(t)})" for n,m,d,pl,t in flags)+'. Check runways and facilities before resuming normal work.'
else: flag='No airport is within 100 km of a magnitude 5.0 or stronger earthquake in the last 24 hours.'
def brg(a,b,c,d):
    p1,p2=math.radians(a),math.radians(c); dl=math.radians(d-b)
    y=math.sin(dl)*math.cos(p2); x=math.cos(p1)*math.sin(p2)-math.sin(p1)*math.cos(p2)*math.cos(dl)
    return (math.degrees(math.atan2(y,x))+360)%360
C8=['north','northeast','east','southeast','south','southwest','west','northwest']
def comp(b): return C8[int((b+22.5)//45)%8]
DIRW={'N':'north','NNE':'north-northeast','NE':'northeast','ENE':'east-northeast','E':'east','ESE':'east-southeast','SE':'southeast','SSE':'south-southeast','S':'south','SSW':'south-southwest','SW':'southwest','WSW':'west-southwest','W':'west','WNW':'west-northwest','NW':'northwest','NNW':'north-northwest'}
def ll(mm):
    la=int(mm.group(2)[:2])+int(mm.group(2)[2:])/60; lo=int(mm.group(4)[:3])+int(mm.group(4)[3:])/60
    return (la if mm.group(1)=='N' else -la, lo if mm.group(3)=='E' else -lo)
storms=[]; tyok=True; ty_time=None; area_hits=[]
try:
    SG=SIGMET or []; seen={}
    if SIGMET is None and GDACS is None and JMATC is None: raise RuntimeError('no typhoon source reached')
    for x in SG:
        if x.get('hazard')!='TC' or x.get('validTimeTo',0)<NOW.timestamp(): continue
        raw=' '.join(x['rawSigmet'].split()); nm=re.search(r'\bTC ([A-Z][A-Z-]+)',raw); ps=list(re.finditer(r'\b([NS])(\d{4}) ?([EW])(\d{5})\b',raw))
        if not nm or not ps: continue
        la,lo=ll(ps[0])
        if not (0<=la<=45 and 100<=lo<=180): continue
        fc=None; mf=re.search(r'FCST AT .*?([NS])(\d{4}) ?([EW])(\d{5})',raw)
        if mf: fc=ll(mf)
        name='-'.join(w.capitalize() for w in nm.group(1).split('-'))
        if name in seen and seen[name]['rt']>=x['receiptTime']: continue
        near=min(rows,key=lambda r:hav(la,lo,r['lat'],r['lon'])); dist=hav(la,lo,near['lat'],near['lon'])
        trend=None
        if fc:
            d2=min(hav(fc[0],fc[1],r['lat'],r['lon']) for r in rows); trend='getting closer to the Philippines' if d2<dist-10 else 'moving away from the Philippines' if d2>dist+10 else 'staying about the same distance from the Philippines'
        mv=DIRW.get(x.get('dir') or ''); sp=round(float(x['spd'])*1.852) if x.get('spd') else None
        if not mv and fc and hav(la,lo,fc[0],fc[1])>20: mv=comp(brg(la,lo,fc[0],fc[1]))
        seen[name]=dict(rt=x['receiptTime'],name=name,la=la,lo=lo,dist=dist,near=near['name'],side=comp(brg(near['lat'],near['lon'],la,lo)),mv=mv,sp=sp,chg={'INTSF':'strengthening','WKN':'weakening','NC':'holding steady'}.get(x.get('chng')),trend=trend,inpar=(5<=la<=25 and 115<=lo<=135))
    for g in []:      # GDACS is now merged in the cross-check block further down
        la,lo=g['la'],g['lo']
        if not (0<=la<=45 and 100<=lo<=180): continue
        near=min(rows,key=lambda r:hav(la,lo,r['lat'],r['lon'])); dist=hav(la,lo,near['lat'],near['lon'])
        seen[g['name']]=dict(rt='',name=g['name'],la=la,lo=lo,dist=dist,near=near['name'],side=comp(brg(near['lat'],near['lon'],la,lo)),mv=None,sp=None,chg=None,trend=None,inpar=(5<=la<=25 and 115<=lo<=135))
    storms=sorted(seen.values(),key=lambda z:z['dist'])
    def inside(la,lo,poly):
        n=len(poly); c=False; j=n-1
        for i in range(n):
            yi,xi=poly[i]; yj,xj=poly[j]
            if ((yi>la)!=(yj>la)) and (lo<(xj-xi)*(la-yi)/(yj-yi)+xi): c=not c
            j=i
        return c
    for x in SG:
        if x.get('hazard') not in ('TS','TC') or not x.get('coords'): continue
        if not (x.get('validTimeFrom',0)<=NOW.timestamp()+3600 and x.get('validTimeTo',0)>NOW.timestamp()): continue
        cs=x['coords']; polys=[]
        for pc in (cs if isinstance(cs[0],list) else [cs]):
            pp=[(c['lat'],c['lon']) for c in pc if isinstance(c,dict) and c.get('lat') is not None and c.get('lon') is not None]
            if len(pp)>=3: polys.append(pp)
        if not polys: continue
        if x['hazard']=='TS':
            for pp in polys:
                if any(0<=la<=25 and 110<=lo<=135 for la,lo in pp):
                    TS_AREAS.append(dict(a=int(x.get('validTimeFrom',0))*1000,b=int(x['validTimeTo'])*1000,p=[[round(P['cx'][0]*lo+P['cx'][1],1),round(P['cy'][0]*la+P['cy'][1],1)] for la,lo in pp]))
        vt=dt.datetime.fromtimestamp(x['validTimeTo'],dt.timezone.utc); kind='Tropical cyclone' if x['hazard']=='TC' else 'Thunderstorm'
        for r in rows:
            if r.get('_area') or not any(inside(r['lat'],r['lon'],pp) for pp in polys): continue
            r['_area']=True; area_hits.append(r['name'])
            r['next']=f"Official {kind.lower()} area warning covers this airport until {clock(vt)}. "+r['next']
            if r['level'] in ('normal','advisory','nodata'):
                r['level']='warning'; r['what']=f'{kind} area warning'; r['when']='Now, until '+clock(vt); r['sort']=0; r['todo']=TODO['warning']
            if r['est']: r['conf']='Medium: an official '+kind.lower()+' area warning covers this airport. Local rain and wind are still an estimate (MET Norway).'
except Exception as e:
    tyok=False; print('SIGMET ERROR',e,file=sys.stderr)
def km(d): return f"{int(round(d/10)*10):,}"
def sdesc(z):
    t=f"{z['name']} is about {km(z['dist'])} km {z['side']} of {z['near']}"
    if z['mv']: t+=f", moving {z['mv']}"+(f" at {z['sp']} km/h" if z['sp'] else '')
    if z['chg']: t+=f" and {z['chg']}"
    t+='.'
    if z['trend']: t+=f" It is {z['trend']}."
    return t
inp=[z for z in storms if z['inpar']]; outp=[z for z in storms if not z['inpar']]
if not tyok:
    ty_main=ty_pa='Aviation storm warnings could not be reached at this check, so the typhoon watch is not available.'; ty_banner='Typhoon watch not available at this check'
else:
    if inp:
        lead=' '.join('Tropical cyclone '+sdesc(z) for z in inp); ty_banner='Typhoon watch: '+', '.join(z['name'] for z in inp)+' in the Philippine area'
        pa_lead='In the Philippine area: '+'; '.join(f"{z['name']}, {km(z['dist'])} km {z['side']} of {z['near']}" for z in inp)+'.'
    else: lead='No typhoon or storm is in the Philippine area now.'; pa_lead=lead; ty_banner='No typhoon in the Philippine area today'
    if outp:
        ty_main=lead+' Tropical cyclones being tracked in the western Pacific: '+' '.join(sdesc(z) for z in outp)+('' if SIGMET is not None else ' This backup source shows position only, not movement.')
        short=[f"{z['name']}, {km(z['dist'])} km {z['side']}"+(f", {z['trend'].replace(' to the Philippines','').replace(' from the Philippines','').replace(' from the Philippines','')}" if z['trend'] else '') for z in outp[:2]]
        ty_pa=pa_lead+' Tracked in the Pacific: '+'; '.join(short)+('.' if len(outp)<=2 else f"; and {len(outp)-2} more farther away.")
    else:
        ty_main=lead+(' No other storms are being tracked in the western Pacific.' if not inp else ''); ty_pa=pa_lead+('' if inp else ' None tracked in the western Pacific.')
# =====================================================================================
# TYPHOON STAGES, CROSS-CHECK AND ALERTS
# Three independent sources are compared at every check:
#   Aviation storm warnings (SIGMET) : position, movement, and the warning areas
#   RSMC Tokyo (JMA)                 : strength, how far the strong winds reach, 24-hour forecast position
#   GDACS (UN and EU)                : position and a second wind figure
# A cyclone counts as CONFIRMED only when at least two of the three report it. Only confirmed cyclones
# appear in the banner, on the map and in alerts. A cyclone reported by one source is mentioned as
# "not yet confirmed" and raises no alert.
#
# Stage (PAGASA scale, 10-minute winds): Tropical Depression up to 61 km/h, Tropical Storm 62-88,
# Severe Tropical Storm 89-117, Typhoon 118-184, Super Typhoon 185 or more.
#
# Alert rule. CAAP and PAGASA act on Tropical Cyclone Wind Signals, which are based on when strong
# winds will arrive (Signal 1: 39-61 km/h within 36 hours; Signal 2: 62-88 km/h within 24 hours), not
# on a fixed distance. The signals are not published as data, so the closest measurable equivalent is
# used: the reach of strong winds (30 knots, about 55 km/h) reported by RSMC Tokyo.
#   Strong winds now      : an airport is inside the strong-wind area of a Tropical Storm or stronger.
#   Expected in 24 hours  : an airport is inside that area at the 24-hour forecast position.
#   TY_NEAR_KM            : used only when the reach is not given.
TY_NEAR_KM = 300
STAGES = [(185, 'STY', 'Super Typhoon'), (118, 'TY', 'Typhoon'), (89, 'STS', 'Severe Tropical Storm'), (62, 'TS', 'Tropical Storm'), (0, 'TD', 'Tropical Depression')]
def stage_of(kmh):
    for lim, code, word in STAGES:
        if kmh is not None and kmh >= lim: return code, word
    return '', 'Tropical cyclone'
CYCLONES = []; TY_ALERTS = []
try:
    if not tyok: raise RuntimeError('typhoon watch not available')
    _c = [dict(z, src=['sigmet'], jma=None, gd=None) for z in storms]
    def _match(name, la, lo):
        for c in _c:
            if name and c['name'] and name.lower() == c['name'].lower() and hav(la, lo, c['la'], c['lo']) <= 1000: return c      # same name and roughly the same place
        near = [c for c in _c if hav(la, lo, c['la'], c['lo']) <= 300]
        return min(near, key=lambda c: hav(la, lo, c['la'], c['lo'])) if near else None
    def _new(name, la, lo):
        nr = min(rows, key=lambda r: hav(la, lo, r['lat'], r['lon']))
        c = dict(rt='', name=name, la=la, lo=lo, dist=hav(la, lo, nr['lat'], nr['lon']), near=nr['name'], side=comp(brg(nr['lat'], nr['lon'], la, lo)), mv=None, sp=None, chg=None, trend=None,
                 inpar=(5 <= la <= 25 and 115 <= lo <= 135), src=[], jma=None, gd=None)
        _c.append(c); return c
    for j in (JMATC or []):
        if not (0 <= j['la'] <= 45 and 100 <= j['lo'] <= 180): continue
        c = _match(j['name'], j['la'], j['lo']) or _new(j['name'] or 'Unnamed', j['la'], j['lo'])
        if 'jma' not in c['src']: c['src'].append('jma')
        c['jma'] = j
        if not c['name'] or c['name'] == 'Unnamed': c['name'] = j['name'] or c['name']
    for g in (GDACS or []):
        if not (0 <= g['la'] <= 45 and 100 <= g['lo'] <= 180): continue
        c = _match(g['name'], g['la'], g['lo']) or _new(g['name'], g['la'], g['lo'])
        if 'gdacs' not in c['src']: c['src'].append('gdacs')
        c['gd'] = g
    _label = {'sigmet': 'aviation storm warnings', 'jma': 'RSMC Tokyo', 'gdacs': 'GDACS'}
    for c in _c:
        j = c['jma']; g = c['gd']
        if j and 'sigmet' not in c['src']:        # no aviation warning: take position and movement from RSMC Tokyo
            c['la'], c['lo'] = j['la'], j['lo']; c['mv'] = j['mv']; c['sp'] = j['sp']
            nr = min(rows, key=lambda r: hav(c['la'], c['lo'], r['lat'], r['lon'])); c['dist'] = hav(c['la'], c['lo'], nr['lat'], nr['lon']); c['near'] = nr['name']; c['side'] = comp(brg(nr['lat'], nr['lon'], c['la'], c['lo']))
            c['inpar'] = (5 <= c['la'] <= 25 and 115 <= c['lo'] <= 135)
            if j['fc']:
                d2 = min(hav(j['fc'][0], j['fc'][1], r['lat'], r['lon']) for r in rows)
                c['trend'] = 'getting closer to the Philippines' if d2 < c['dist'] - 10 else 'moving away from the Philippines' if d2 > c['dist'] + 10 else 'staying about the same distance from the Philippines'
        wind = j['wind'] if j else None; est = False
        if wind is None and g and g.get('wind'): wind = round(g['wind'] * 0.93); est = True       # GDACS quotes 1-minute winds; 10-minute winds are about 7 percent lower
        code, word = stage_of(wind)
        if j and j['cls'] == 'TD' and not code: code, word = 'TD', 'Tropical Depression'
        gale = (j or {}).get('gale'); reach = gale or TY_NEAR_KM
        fc = (j or {}).get('fc')
        strong = code in ('TS', 'STS', 'TY', 'STY')
        now_ap = sorted(r['name'] for r in rows if strong and hav(c['la'], c['lo'], r['lat'], r['lon']) <= reach)
        exp_ap = sorted(r['name'] for r in rows if strong and fc and r['name'] not in now_ap and hav(fc[0], fc[1], r['lat'], r['lon']) <= reach)
        confirmed = len(c['src']) >= 2
        title = (word + ' ' + c['name']) if c['name'] and c['name'] != 'Unnamed' else word
        pos = f"about {km(c['dist'])} km {c['side']} of {c['near']}"
        move = ((f"moving {c['mv']}" + (f" at {c['sp']} km/h" if c['sp'] else '')) if c['mv'] else ('almost stationary' if (j or {}).get('still') else ''))
        windline = (f"Maximum winds about {wind} km/h near the centre" + (f", gusts to {j['gust']} km/h" if j and j.get('gust') else '') + ('.' if not est else ' (estimated from GDACS; RSMC Tokyo gave no figure).')) if wind else 'Strength not reported at this check.'
        reachline = (f"Strong winds (about 55 km/h or more) reach up to about {km(gale)} km from the centre." + (f" Storm-force winds (about 90 km/h or more) reach up to about {km(j['storm'])} km." if j and j.get('storm') else '')) if gale else (f"How far the strong winds reach was not reported, so {TY_NEAR_KM} km is used." if strong else '')
        fcline = ''
        if fc:
            fn = min(rows, key=lambda r: hav(fc[0], fc[1], r['lat'], r['lon'])); fd = hav(fc[0], fc[1], fn['lat'], fn['lon'])
            fcode, fword = stage_of((j or {}).get('wind24'))
            fcline = f"In 24 hours it is forecast to be about {km(fd)} km {comp(brg(fn['lat'], fn['lon'], fc[0], fc[1]))} of {fn['name']}" + (f" as a {fword}" if fcode else '') + (f" ({j['wind24']} km/h)" if (j or {}).get('wind24') else '') + '.'
        cross = 'Reported by ' + ', '.join(_label[k] for k in c['src'][:-1]) + (' and ' if len(c['src']) > 1 else '') + _label[c['src'][-1]] + '.'
        if g and g.get('wind') and j and j.get('wind'): cross += f" GDACS gives {round(g['wind'])} km/h, measured over 1 minute, which normally reads higher than the 10-minute figure used here."
        if not confirmed: cross += ' Not yet confirmed by a second source, so it raises no alert.'
        if now_ap: todo = f"Strong winds from {title} can reach {', '.join(now_ap)}. Secure loose equipment and aircraft, follow the station typhoon plan, and watch PAGASA wind signals and CAAP and airline advisories."
        elif exp_ap: todo = f"{title} is forecast to bring strong winds to {', '.join(exp_ap)} within about 24 hours. Prepare the station typhoon plan and watch PAGASA wind signals and CAAP and airline advisories."
        elif c['inpar']: todo = 'No airport is inside the strong-wind area at this check. Keep watching PAGASA bulletins.'
        else: todo = 'No action needed.'
        if not confirmed and (now_ap or exp_ap): todo = f"Not yet confirmed: only one source is reporting {title}, so no alert has been sent. If it is confirmed, strong winds could reach {', '.join(now_ap or exp_ap)}. Check the PAGASA bulletin before acting."
        x_ = P['cx'][0] * c['lo'] + P['cx'][1]; y_ = P['cy'][0] * c['la'] + P['cy'][1]
        cid = 't' + re.sub(r'[^a-z0-9]', '', c['name'].lower() or 'x') + str(len(CYCLONES))
        CYCLONES.append(dict(id=cid, name=c['name'], title=title, stage=code, word=word, confirmed=confirmed, inpar=c['inpar'], lat=c['la'], lon=c['lo'], x=x_, y=y_, show=(-150 <= x_ <= 250 and -18 <= y_ <= 116), onmap=(0 <= x_ <= 100 and 0 <= y_ <= 100),
            wind=wind, gale=(gale if strong else None), reach=(reach if strong else None), fx=(P['cx'][0] * fc[1] + P['cx'][1] if fc else None), fy=(P['cy'][0] * fc[0] + P['cy'][1] if fc else None),
            now=now_ap, soon=exp_ap, dist=c['dist'], chg=c['chg'], trend=c['trend'],
            where=f"{title} is {pos}" + (f", {move}" if move else '') + (f" and {c['chg']}" if c['chg'] else '') + '.' + (f" It is {c['trend']}." if c['trend'] else ''),
            windline=windline, reachline=reachline, fcline=fcline, cross=cross, todo=todo,
            src='Position and warning areas: aviation storm warnings (aviationweather.gov). Strength, wind reach and forecast: RSMC Tokyo, Japan Meteorological Agency. Cross-check: GDACS.',
            ms=int((j['issued'] if j else NOW).timestamp() * 1000)))
        if confirmed and (now_ap or exp_ap):
            grp = 'STY' if code == 'STY' else 'TY' if code == 'TY' else 'TS'
            kind = 'near' if now_ap else 'soon'
            TY_ALERTS.append(dict(kind=kind, key=f"ty:{c['name'].lower()}:{kind}:{grp}", t=cid, ms=CYCLONES[-1]['ms'],
                text=(f"{title}: strong winds can reach {', '.join(now_ap)}." if now_ap else f"{title}: strong winds expected at {', '.join(exp_ap)} within about 24 hours.") + f" It is {pos}. {windline}"))
    CYCLONES.sort(key=lambda z: (0 if z['confirmed'] else 1, z['dist']))
    TY_ALERTS.sort(key=lambda a: (0 if a['kind'] == 'near' else 1, -a['ms']))
    _conf = [z for z in CYCLONES if z['confirmed']]; _in = [z for z in _conf if z['inpar']]; _out = [z for z in _conf if not z['inpar']]; _un = [z for z in CYCLONES if not z['confirmed']]
    def _full(z): return ' '.join(x for x in (z['where'], z['windline'], z['reachline'], z['fcline']) if x)
    if _in:
        ty_banner = ', '.join(z['title'] for z in _in) + ' in the Philippine area'
        ty_main = ' '.join(_full(z) for z in _in); ty_pa = 'In the Philippine area: ' + '; '.join(f"{z['title']}, {km(z['dist'])} km from the nearest airport" for z in _in) + '.'
    else:
        _unin = [z for z in _un if z['inpar']]
        if _unin:      # never say "no typhoon" while one source is reporting one inside the Philippine area
            ty_banner = ', '.join(z['title'] for z in _unin) + ' reported by one source, awaiting confirmation'
            ty_main = 'No confirmed typhoon or storm is in the Philippine area now, but one source is reporting one. It is listed below as not yet confirmed.'; ty_pa = ty_banner + '.'
        else:
            ty_banner = 'No typhoon in the Philippine area today'; ty_main = 'No typhoon or storm is in the Philippine area now.'; ty_pa = ty_main
    if _out: ty_main += ' Being tracked in the western Pacific: ' + ' '.join(z['where'] + ' ' + z['windline'] for z in _out)
    elif not _in and not [z for z in _un if z['inpar']]: ty_main += ' No other storms are being tracked in the western Pacific.'
    if _un: ty_main += ' Not yet confirmed: ' + ' '.join(f"{z['title']}, {km(z['dist'])} km from the nearest airport, {'r' + z['cross'].split('.')[0][1:]} only." for z in _un) + ' A cyclone is treated as confirmed, and can raise an alert, only after two sources report it.'
    _srcs = [k for k, ok in (('aviation storm warnings', SIGMET is not None), ('RSMC Tokyo', JMATC is not None), ('GDACS', GDACS is not None)) if ok]
    if len(_srcs) < 2: PROBLEMS.append(f"Typhoon watch: only one source could be reached ({_srcs[0] if _srcs else 'none'}), so cyclones cannot be cross-checked at this check.")
except Exception as _e:
    CYCLONES = []; TY_ALERTS = []; print('TYPHOON STAGE ERROR', _e, file=sys.stderr)
T0=MIDNIGHT
for r in rows: r.pop('_area',None)
def common(ts): return Counter(ts).most_common(1)[0][0] if ts else None
ot=common(obs_times); tt=common(taf_times)
nOff=sum(1 for r in rows if not r['est'] and r['level']!='nodata'); nEst=sum(1 for r in rows if r['est'])
if est_times:
    e0=clock_plain(min(est_times)); e1=clock_plain(max(est_times)); et=e1 if e0==e1 else f'{e0} to {e1}'
else: et=None
n=ph(NOW)
parts=[f"Last updated {n.strftime('%A')}, {day(NOW)}, {clock_plain(NOW)}."]
bits=[]
if ot: bits.append(f"Airport reports {clock_plain(ot)}")
if tt: bits.append(f"airport forecasts issued {clock_plain(tt)}")
if et: bits.append(f"estimates updated {et}")
if bits: parts.append(', '.join(bits)[0].upper()+', '.join(bits)[1:]+' (Philippine time).')
parts.append(f"{len(rows)} Cebu Pacific and Cebgo airports in the Philippines.")
src=[]
if nOff: src.append(f"Sources: official airport weather reports{f' ({clock_plain(ot)})' if ot else ''} and airport forecasts{f' (issued {clock_plain(tt)})' if tt else ''} from {SHORT[USED['reports']]} for {nOff} airports.")
else: src.append('Sources: no official airport report could be read at this check.')
if nEst: src.append(f"The {'other ' if nOff else ''}{nEst} airports have no official airport report, so they use the {' or '.join(sorted(set(r['estsrc'] for r in rows if r['est'])))} location forecast{f' (updated {et})' if et else ''} and are marked Estimate.")
src.append("Estimates show rain and wind only and cannot confirm thunderstorms, so an Estimate airport is never shown as Danger. For Estimates, bad weather means moderate or heavy rain (2.5 mm or more in an hour), or winds of 39 km/h or more. Tomorrow and days-ahead outlooks use the same airport forecasts and MET Norway estimates and are less certain than today's alerts.")
if not tyok: src.append("Typhoon watch: no typhoon source could be reached at this check.")
else: src.append("Typhoon watch compares three sources, checked " + clock_plain(NOW) + ": aviation storm warnings (position, movement, warning areas), RSMC Tokyo of the Japan Meteorological Agency (strength, how far strong winds reach, 24-hour forecast) and GDACS (cross-check). Reached at this check: " + (', '.join(k for k, ok in (('aviation storm warnings', SIGMET is not None), ('RSMC Tokyo', JMATC is not None), ('GDACS', GDACS is not None)) if ok) or 'none') + ". A cyclone is shown and alerted only when at least two of them report it.")
src.append(f"Earthquakes are from {QSRC} (magnitude 4.5 and stronger), data as of {day(asof)}, {clock_plain(asof)}." if asof else "Earthquake data could not be reached at this check.")
src.append("Accuracy ranking, highest first: 1) official airport report, 2) official airport forecast, 3) official aviation area warning, 4) computer forecast estimate. The moving rain layer on the map is a MET Norway forecast, rebuilt every few hours; it is a picture of the forecast and plays no part in the alert levels. When sources differ the higher-ranked one is used, and each airport's details show its confidence. If a source cannot be reached, its backup is used automatically and the Data sources table shows which one supplied the data. Times are Philippine time.")
# ---------- backup self-test ----------
# Backups are rarely used, so a broken one could go unnoticed until the day it is needed.
# Every few hours each idle backup is tried once with a small request and the result is kept
# in data.json (shown in the Help window). This never changes which source the dashboard uses.
TEST_EVERY_HOURS = 6
try:
    with open(OUT, encoding='utf-8') as _f: _prev_tests = json.load(_f).get('backup_tests', {}) or {}
except Exception:
    _prev_tests = {}
def _probe(group, key):
    if group == 'reports': return _noaa('metar', only=['RPLL']) if key == 'noaa' else load_reports(key)
    if group == 'forecasts': return _noaa('taf', only=['RPLL']) if key == 'noaa' else load_forecasts(key)
    if group == 'estimates': return EST_LOADERS[key]([a for a in APTS if a[1] == 'RPLL'])
    if group == 'storms': return load_storms(key)
    if group == 'quakes': return load_quakes(key)
BACKUP_TESTS = {}
for _g in SOURCE_ORDER:
    for (_k, _st, _note) in STATUS[_g]:
        if _st != 'standby': continue
        _tid = _g + ':' + _k; _old = _prev_tests.get(_tid)
        if _old and NOW.timestamp() * 1000 - _old.get('ms', 0) < TEST_EVERY_HOURS * 3.6e6: BACKUP_TESTS[_tid] = _old; continue
        try: _ok = bool(_probe(_g, _k))
        except Exception as _e:
            print('BACKUP TEST ERROR', _tid, _e, file=sys.stderr); _ok = False
        BACKUP_TESTS[_tid] = dict(ok=_ok, ms=int(NOW.timestamp() * 1000), when=f"{day(NOW)}, {clock_plain(NOW)}")
        print('Backup test', _tid, 'OK' if _ok else 'FAILED')
def _chain_entry(g, i, k, st, note):
    t = BACKUP_TESTS.get(g + ':' + k) if st == 'standby' else None
    if t: note = ('Backup, last tested OK ' if t['ok'] else 'Backup, last test failed ') + t['when']
    return dict(name=SOURCE_NAMES[k], role=ROLE[min(i, 3)], state=st, note=note, tested=(None if not t else ('ok' if t['ok'] else 'failed')))
ROLE=['First choice','Backup','Second backup','Third backup']
SRC_STATUS=[]
for g in SOURCE_ORDER:
    SRC_STATUS.append(dict(what=GROUP_LABEL[g], used=(SOURCE_NAMES[USED[g]] if USED[g] else 'None reached'), ok=bool(USED[g]), first=(USED[g]==SOURCE_ORDER[g][0]),
        chain=[_chain_entry(g,i,k,st,note) for i,(k,st,note) in enumerate(STATUS[g])]))
for _b in SRC_STATUS:
    if _b['what'] == GROUP_LABEL['storms']:
        _roles = {SOURCE_NAMES['sigmet']: 'Position, movement and warning areas', SOURCE_NAMES['jma']: 'Strength, wind reach and forecast', SOURCE_NAMES['gdacs']: 'Cross-check'}
        for _ce in _b['chain']: _ce['role'] = _roles.get(_ce['name'], _ce['role'])
        _n = sum(1 for _ce in _b['chain'] if _ce['state'] == 'used')
        _b['used'] = f'{_n} of 3 sources reached'; _b['ok'] = _n >= 1; _b['first'] = _n >= 2
# Times of the most recent refreshes, so the page can learn how often the schedule really runs
# and show a realistic "next update" time (the hosting schedule often starts late).
try:
    with open(OUT, encoding='utf-8') as _f: _pd = json.load(_f)
    RECENT = [int(x) for x in (_pd.get('recent') or [])]
    if _pd.get('generated_ms') and int(_pd['generated_ms']) not in RECENT: RECENT.append(int(_pd['generated_ms']))
except Exception:
    RECENT = []
RECENT = sorted(set(RECENT + [int(NOW.timestamp()*1000)]))[-13:]
# =====================================================================================
# VOLCANOES
# Works like the earthquake part: it never changes an airport's weather level. It adds
# volcano markers, an ash-cloud layer, and volcano alerts for the alert bar and notifications.
#
# Sources
#   Ash clouds and eruptions : official aviation volcanic-ash warnings (SIGMET) from aviationweather.gov,
#                              the same feed already read for typhoons and thunderstorm areas.
#   Volcano Alert Level (0-5): PHIVOLCS volcano bulletins. If they cannot be read with confidence,
#                              the levels typed into volcano_levels.json are used instead.
#
# Rules (see the Help Centre)
#   VOLC_KM       : a volcano is "near" an airport within this distance. There is no official
#                   standard; 150 km covers about half of all past airport disruptions (USGS study).
#   Ash alert     : an official ash-warning area covers an airport, at any distance from the volcano.
#   Eruption alert: an ash warning names an eruption at a volcano within VOLC_KM of an airport.
#   Level alert   : a volcano within VOLC_KM of an airport is at LEVEL_ALERT or higher.
# =====================================================================================
VOLC_KM = 150
LEVEL_ALERT = 3
VOLCANOES = [   # id, name, latitude, longitude, shown on the map at all times (the closely monitored ones)
    ('mayon', 'Mayon', 13.257, 123.685, True), ('taal', 'Taal', 14.002, 120.993, True), ('kanlaon', 'Kanlaon', 10.412, 123.132, True),
    ('bulusan', 'Bulusan', 12.770, 124.050, True), ('pinatubo', 'Pinatubo', 15.130, 120.350, True), ('hibokhibok', 'Hibok-Hibok', 9.203, 124.673, True),
    ('parker', 'Parker', 6.113, 124.892, False), ('matutum', 'Matutum', 6.370, 125.070, False), ('banahaw', 'Banahaw', 14.070, 121.480, False),
    ('iriga', 'Iriga', 13.457, 123.457, False), ('isarog', 'Isarog', 13.658, 123.380, False), ('biliran', 'Biliran', 11.523, 124.535, False),
    ('cabalian', 'Cabalian', 10.287, 125.221, False), ('musuan', 'Musuan', 7.877, 125.068, False), ('makaturing', 'Makaturing', 7.647, 124.320, False),
    ('ragang', 'Ragang', 7.690, 124.500, False), ('leonardkniaseff', 'Leonard Kniaseff', 7.382, 126.047, False), ('buddajo', 'Bud Dajo', 6.013, 121.057, False),
    ('cagua', 'Cagua', 18.222, 122.123, False), ('camiguindebabuyanes', 'Camiguin de Babuyanes', 18.830, 121.860, False), ('didicas', 'Didicas', 19.077, 122.202, False),
    ('babuyanclaro', 'Babuyan Claro', 19.523, 121.940, False), ('iraya', 'Iraya', 20.469, 122.010, False),
]
LEVEL_WORDS = {0: 'Normal. Quiet, no eruption expected soon.', 1: 'Low-level unrest. Small steam or gas-driven bursts are possible near the crater.',
               2: 'Increasing unrest. Activity is rising and could lead to an eruption.', 3: 'High unrest. A hazardous eruption is possible within weeks.',
               4: 'Hazardous eruption imminent, possible within hours to days.', 5: 'Hazardous eruption in progress.'}
VOLC_LEVELS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'volcano_levels.json')

def _phiv_volcano_levels():
    """Try to read the current Alert Level of each volcano from the PHIVOLCS bulletin pages.
    Returns {volcano id: (level, 'as of' text)}. Anything not read with confidence is left out."""
    out = {}
    base = 'https://wovodat.phivolcs.dost.gov.ph'
    page = fetch(base + '/bulletin/list-of-bulletin', tries=1, text=True, insecure_ok=True, timeout=30)
    if not page:
        print('VOLCANO: PHIVOLCS bulletin list not reached.', file=sys.stderr); return out
    anchors = re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, flags=re.S | re.I)
    print(f'VOLCANO: bulletin list read, {len(page)} characters, {len(anchors)} links.', file=sys.stderr)
    tried = 0
    for vid, vname, _la, _lo, _main in VOLCANOES:
        link = None
        for href, label in anchors:
            lab = ' '.join(re.sub(r'<[^>]+>', ' ', label).split())
            if re.search(r'\b' + re.escape(vname) + r'\b', lab, re.I) and re.search(r'summary|observation|bulletin|advisory', lab, re.I): link = href; break
        if not link:
            m = re.search(re.escape(vname) + r'\s+Volcano\s+Summary', page, re.I)
            if m:
                near = re.findall(r'href=["\']([^"\']+)["\']', page[max(0, m.start() - 600):m.end() + 900])
                near = [h for h in near if re.search(r'bulletin|activity|vhub|bid=|\.pdf', h, re.I)]
                if near: link = near[0]
        if not link or tried >= 8: continue
        tried += 1
        url = link if link.startswith('http') else base + ('' if link.startswith('/') else '/') + link
        if url.lower().endswith('.pdf'): print(f'VOLCANO: {vname} bulletin is a PDF, not read: {url}', file=sys.stderr); continue
        body = fetch(url, tries=1, text=True, insecure_ok=True, timeout=30)
        if not body: print(f'VOLCANO: {vname} bulletin not reached: {url}', file=sys.stderr); continue
        txt = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', body, flags=re.S | re.I); txt = ' '.join(re.sub(r'<[^>]+>', ' ', txt).replace('&nbsp;', ' ').split())
        lv = re.findall(r'Alert\s+Level\s*:?\s*([0-5])\b', txt, re.I)
        dm = re.search(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', txt)
        print(f"VOLCANO: {vname}: levels seen {lv[:6]}, date {dm.group(0) if dm else None}, text sample: {txt[:160]!r}", file=sys.stderr)
        if not lv or not dm: continue
        try: bd = dt.datetime.strptime(dm.group(0), '%d %B %Y').replace(tzinfo=PHT)
        except Exception: continue
        if abs((NOW - bd).days) > 4: print(f'VOLCANO: {vname} bulletin is not recent ({dm.group(0)}); not used.', file=sys.stderr); continue
        if len(set(lv[:3])) != 1: print(f'VOLCANO: {vname} bulletin mentions several levels; not used.', file=sys.stderr); continue
        out[vid] = (int(lv[0]), f"PHIVOLCS bulletin, {dm.group(0)}")
    return out

VAAC_HOURS = 6        # a Tokyo VAAC advisory counts as current for this long (the same length as an aviation ash warning)
VAAC_LIST = 'https://ds.data.jma.go.jp/svd/vaac/data/vaac_list.html'
def _tokyo_vaac():
    """Second source for eruptions and ash: the Tokyo Volcanic Ash Advisory Centre (Japan Meteorological Agency), the official
    centre for ash advisories over the Philippines. Returns the current advisories for volcanoes in the Philippine region,
    newest first, or None when the site could not be read. Prints lines starting with VAAC: so a run log shows what was found."""
    page = fetch(VAAC_LIST, tries=2, text=True, timeout=30)
    if not page: print('VAAC: advisory list not reached.', file=sys.stderr); return None
    links = re.findall(r'TextData/(\d{4})/((\d{8})_(\d{6,8})_(\d{3,4})_Text\.html)', page)
    print(f'VAAC: advisory list read, {len(page)} characters, {len(links)} advisories listed.', file=sys.stderr)
    if not links: return None
    out = []; seen = set(); tried = 0
    for year, fname, ymd, vnum, _no in links:
        if not vnum.startswith('27') or fname in seen: continue             # 27xxxx = volcanoes of the Philippines and South-East Asia
        seen.add(fname)
        try: d0 = dt.datetime.strptime(ymd, '%Y%m%d').replace(tzinfo=dt.timezone.utc)
        except Exception: continue
        if (NOW - d0).total_seconds() > (VAAC_HOURS + 24) * 3600: continue      # the file name only has the date, so allow a day here
        if tried >= 6: break
        tried += 1
        body = fetch(f'https://ds.data.jma.go.jp/svd/vaac/data/TextData/{year}/{fname}', tries=1, text=True, timeout=25)
        if not body: print(f'VAAC: advisory not reached: {fname}', file=sys.stderr); continue
        txt = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', body, flags=re.S | re.I)
        txt = re.sub(r'<br\s*/?>|</p>|</div>|</pre>', '\n', txt, flags=re.I); txt = html.unescape(re.sub(r'<[^>]+>', ' ', txt))
        def field(label):
            m = re.search(label + r'\s*:\s*(.*?)(?=\s*(?:DTG|VAAC|VOLCANO|PSN|AREA|SOURCE ELEV|SUMMIT ELEV|ADVISORY NR|INFO SOURCE|AVIATION COLOU?R CODE|ERUPTION DETAILS|OBS VA DTG|OBS VA CLD|EST VA DTG|EST VA CLD|FCST VA CLD[^:\n]*|RMK|NXT ADVISORY)\s*:|=|\Z)', txt, re.S)
            return ' '.join(m.group(1).split()) if m else ''
        m = re.search(r'DTG\s*:\s*(\d{8})/(\d{4})Z', txt); ps = re.search(r'PSN\s*:\s*([NS])(\d{4})\s*([EW])(\d{5})', txt)
        if not m or not ps: print(f'VAAC: advisory not understood: {fname}', file=sys.stderr); continue
        dtg = dt.datetime.strptime(m.group(1) + m.group(2), '%Y%m%d%H%M').replace(tzinfo=dt.timezone.utc)
        if not (0 <= (NOW - dtg).total_seconds() <= VAAC_HOURS * 3600): continue
        conv = lambda h, v: (1 if h in 'NE' else -1) * (int(v[:-2]) + int(v[-2:]) / 60.0)
        pos = (conv(ps.group(1), ps.group(2)), conv(ps.group(3), ps.group(4)))
        if not (2 <= pos[0] <= 23 and 112 <= pos[1] <= 132): continue
        erupt = field('ERUPTION DETAILS'); cloud = field('OBS VA CLD'); nr = field('ADVISORY NR'); name = re.sub(r'\s*\d{5,}.*$', '', field('VOLCANO')).strip()
        et = re.search(r'(\d{8})/(\d{4})Z', erupt)
        when = dt.datetime.strptime(et.group(1) + et.group(2), '%Y%m%d%H%M').replace(tzinfo=dt.timezone.utc) if et else None
        seen_cloud = bool(cloud) and not re.search(r'NOT IDENTIFIABLE|NOT OBSERVED|NO VA|\bNIL\b', cloud)
        poly = [(conv(a, b), conv(c, e)) for a, b, c, e in re.findall(r'([NS])(\d{4})\s*([EW])(\d{5})', cloud)] if seen_cloud else []
        top = re.search(r'FL(\d{3})', cloud) if seen_cloud else None
        print(f"VAAC: {name} advisory {nr}, issued {dtg.strftime('%d %b %H:%MZ')}, eruption: {erupt[:60]!r}, cloud seen: {seen_cloud}, area points: {len(poly)}", file=sys.stderr)
        out.append(dict(name=name, pos=pos, dtg=dtg, when=when, nr=nr, erupt=erupt, cloud_seen=seen_cloud, poly=(poly if len(poly) >= 3 else []), top=(int(top.group(1)) if top else None)))
    out.sort(key=lambda a: a['dtg'], reverse=True)
    return out

def _manual_volcano_levels():
    """Levels typed by hand into volcano_levels.json (used when PHIVOLCS cannot be read)."""
    out = {}
    try:
        j = json.load(open(VOLC_LEVELS_FILE, encoding='utf-8'))
        for vid, vname, _la, _lo, _main in VOLCANOES:
            e = (j.get('levels') or {}).get(vname)
            if isinstance(e, dict) and isinstance(e.get('level'), int) and 0 <= e['level'] <= 5:
                out[vid] = (e['level'], 'entered by hand' + (f", as of {e['as_of']}" if e.get('as_of') else ''))
    except FileNotFoundError: pass
    except Exception as e: print('VOLCANO: volcano_levels.json could not be read:', e, file=sys.stderr)
    return out

volcanoes = []; ASH_AREAS = []; VOL_ALERTS = []; vol_ok = True; vol_level_src = ''; VAAC = None
try:
    _auto = {}
    try: _auto = _phiv_volcano_levels()
    except Exception as _e: print('VOLCANO LEVEL ERROR', _e, file=sys.stderr)
    _manual = _manual_volcano_levels()
    V = {}
    for vid, vname, la, lo, main in VOLCANOES:
        lvl = _auto.get(vid) or _manual.get(vid)
        V[vid] = dict(id=vid, name=vname, lat=la, lon=lo, main=main, level=(lvl[0] if lvl else None), level_asof=(lvl[1] if lvl else ''), erupt=False, ash=[], until=None, ms=0, hits=[], by='', vaac=None)
    vol_level_src = 'PHIVOLCS volcano bulletins' if _auto else ('levels entered by hand (volcano_levels.json)' if _manual else '')
    try: VAAC = _tokyo_vaac()
    except Exception as _e: print('VAAC ERROR', _e, file=sys.stderr); VAAC = None
    if SIGMET is None and VAAC is None: vol_ok = False           # neither ash source could be reached
    elif SIGMET is None: PROBLEMS.append('Volcanoes: the aviation ash warnings could not be reached, so the second source (Tokyo VAAC) is being used.')
    for x in (SIGMET or []):
        if x.get('hazard') != 'VA': continue
        if not (x.get('validTimeFrom', 0) <= NOW.timestamp() + 3600 and x.get('validTimeTo', 0) > NOW.timestamp()): continue
        raw = ' '.join((x.get('rawSigmet') or '').split())
        if re.search(r'\bCNL\b|\bCANCEL', raw): continue
        nm = re.search(r'\bMT\.? ([A-Z][A-Z\' -]*?)(?= PSN| LOC| VA | OBS|$)', (x.get('qualifier') or '') + ' ' + raw)
        vname = ' '.join(w.capitalize() for w in nm.group(1).replace('-', ' - ').split()).replace(' - ', '-') if nm else ''
        ps = re.search(r'PSN ([NS])(\d{4}) ?([EW])(\d{5})', raw); pos = ll(ps) if ps else None
        polys = []; cs = x.get('coords') or []
        if cs:
            for pc in (cs if isinstance(cs[0], list) else [cs]):
                pp = [(c['lat'], c['lon']) for c in pc if isinstance(c, dict) and c.get('lat') is not None and c.get('lon') is not None]
                if len(pp) >= 3: polys.append(pp)
        pts = [q for pp in polys for q in pp] + ([pos] if pos else [])
        if not (x.get('firId') == 'RPHI' or any(2 <= la <= 23 and 112 <= lo <= 132 for la, lo in pts)): continue
        # which volcano
        vid = None; key = re.sub(r'[^a-z]', '', vname.lower())
        for v in V.values():
            if key and (key == re.sub(r'[^a-z]', '', v['name'].lower()) or key in re.sub(r'[^a-z]', '', v['name'].lower())): vid = v['id']; break
        if vid is None and pos:
            best = min(V.values(), key=lambda v: hav(pos[0], pos[1], v['lat'], v['lon']))
            if hav(pos[0], pos[1], best['lat'], best['lon']) <= 30: vid = best['id']
        if vid is None:
            if not pos and not polys: continue
            # a volcano outside the Philippines is only of interest when its ash is within reach of one of our airports
            if min(hav(la, lo, r['lat'], r['lon']) for la, lo in pts for r in rows) > 300: continue
            p0 = pos or polys[0][0]; vid = 'x' + (key or 'unnamed')
            V.setdefault(vid, dict(id=vid, name=vname or 'Unnamed volcano', lat=p0[0], lon=p0[1], main=False, level=None, level_asof='', erupt=False, ash=[], until=None, ms=0, hits=[]))
        v = V[vid]; vt = dt.datetime.fromtimestamp(x['validTimeTo'], dt.timezone.utc)
        v['erupt'] = True; v['by'] = 'sigmet'; v['ms'] = max(v['ms'], int(x.get('validTimeFrom', 0)) * 1000)
        if v['until'] is None or vt > v['until']: v['until'] = vt
        top = x.get('top'); mv = DIRW.get(x.get('dir') or ''); sp = round(float(x['spd']) * 1.852) if str(x.get('spd') or '').replace('.', '', 1).isdigit() else None
        desc = ('Ash cloud' + (f" up to about {int(round(float(top) * 0.3048 / 100) * 100):,} m high" if top else '') + (f", moving {mv}" + (f" at {sp} km/h" if sp else '') if mv else '') + '.')
        if desc not in v['ash']: v['ash'].append(desc)
        for pp in polys:
            if any(0 <= la <= 25 and 110 <= lo <= 135 for la, lo in pp):
                ASH_AREAS.append(dict(v=vid, name=v['name'], b=int(x['validTimeTo']) * 1000, p=[[round(P['cx'][0] * lo + P['cx'][1], 1), round(P['cy'][0] * la + P['cy'][1], 1)] for la, lo in pp]))
            for r in rows:
                if r['name'] not in v['hits'] and inside(r['lat'], r['lon'], pp): v['hits'].append(r['name'])
    def _in_area(la, lo, pp):
        """Is the point inside the area? (pp is a list of (lat, lon) corners.)"""
        hit = False; n = len(pp)
        for i in range(n):
            (y1, x1), (y2, x2) = pp[i], pp[(i + 1) % n]
            if (y1 > la) != (y2 > la) and lo < (x2 - x1) * (la - y1) / (y2 - y1) + x1: hit = not hit
        return hit
    # Second source: Tokyo VAAC. It confirms what the aviation warning says, and stands in for it when the
    # warning has not been issued yet or could not be reached.
    for adv in (VAAC or []):
        best = min(V.values(), key=lambda v: hav(adv['pos'][0], adv['pos'][1], v['lat'], v['lon']))
        if hav(adv['pos'][0], adv['pos'][1], best['lat'], best['lon']) > 30: continue
        v = best
        if v.get('vaac'): continue                                   # advisories are newest first: keep the latest for each volcano
        v['vaac'] = adv
        if v['erupt']: continue                                      # the aviation warning already covers it
        v['erupt'] = True; v['by'] = 'vaac'; v['ms'] = int((adv['when'] or adv['dtg']).timestamp() * 1000); v['until'] = adv['dtg'] + dt.timedelta(hours=VAAC_HOURS)
        v['ash'].append((f"Eruption reported at {clock(adv['when'])}. " if adv['when'] else 'Eruption reported. ') +
                        (('Ash cloud observed' + (f" up to about {int(round(adv['top'] * 100 * 0.3048 / 100) * 100):,} m high" if adv['top'] else '') + '.') if adv['cloud_seen'] else 'The ash cloud could not be seen by satellite.'))
        if adv['poly']:
            pp = adv['poly']
            ASH_AREAS.append(dict(v=v['id'], name=v['name'], b=int(v['until'].timestamp() * 1000), p=[[round(P['cx'][0] * lo + P['cx'][1], 1), round(P['cy'][0] * la + P['cy'][1], 1)] for la, lo in pp]))
            for r in rows:
                if r['name'] not in v['hits'] and _in_area(r['lat'], r['lon'], pp): v['hits'].append(r['name'])
    for v in V.values():
        if len(v['ash']) > 1 and 'Ash cloud.' in v['ash']: v['ash'].remove('Ash cloud.')
        nearby = sorted([(hav(v['lat'], v['lon'], r['lat'], r['lon']), r['name']) for r in rows]); close = [(d_, n_) for d_, n_ in nearby if d_ <= VOLC_KM]
        neartxt = (', '.join(f"{n_} (about {max(10, int(round(d_ / 10) * 10))} km)" for d_, n_ in close) + '.') if close else f"No airport within {VOLC_KM} km. Nearest: {nearby[0][1]}, about {km(nearby[0][0])} km away."
        lvl = v['level']; until = f"{day(v['until'])}, {clock(v['until'])}" if v['until'] else ''
        status = 'erupting' if v['erupt'] else ('unknown' if lvl is None else 'high' if lvl >= 4 else 'raised' if lvl == 3 else 'unrest' if lvl >= 1 else 'quiet')
        x_ = P['cx'][0] * v['lon'] + P['cx'][1]; y_ = P['cy'][0] * v['lat'] + P['cy'][1]
        names = [n_ for _d, n_ in close]; alert = False
        byv = v.get('by') == 'vaac'; adv = v.get('vaac')
        force = (f"Tokyo VAAC advisory issued {clock(adv['dtg'])}, watched until {until}" if byv else f"official ash warning in force until {until}")
        if v['hits']:
            alert = True
            VOL_ALERTS.append(dict(kind='ash', key='ash:' + v['id'] + ':' + ','.join(sorted(v['hits'])), v=v['id'], ms=v['ms'],
                text=f"Volcanic ash {'covers' if byv else 'warning covers'} {', '.join(v['hits'])}: ash from {v['name']} Volcano, {force if byv else 'warning in force until ' + until}. Expect runway and aircraft checks, and follow CAAP and airline instructions."))
        elif v['erupt'] and close:
            alert = True
            VOL_ALERTS.append(dict(kind='eruption', key='eruption:' + v['id'], v=v['id'], ms=v['ms'],
                text=f"Eruption at {v['name']} Volcano: {force}. Airports within {VOLC_KM} km: {neartxt} Ash is not over an airport at this check."))
        elif lvl is not None and lvl >= LEVEL_ALERT and close:
            alert = True
            VOL_ALERTS.append(dict(kind='level', key=f"level:{v['id']}:{lvl}", v=v['id'], ms=int(NOW.timestamp() * 1000),
                text=f"{v['name']} Volcano is at Alert Level {lvl}: {LEVEL_WORDS[lvl]} Airports within {VOLC_KM} km: {neartxt}"))
        if v['hits']: todo = 'Volcanic ash warning over ' + ', '.join(v['hits']) + '. Check runways, aircraft and equipment for ash before normal work continues, and follow CAAP and airline instructions.'
        elif v['erupt'] and close: todo = 'Eruption reported. Stations at ' + ', '.join(names) + ' should watch for ashfall, keep equipment covered where possible, and be ready for flight changes.'
        elif lvl is not None and lvl >= LEVEL_ALERT and close: todo = 'Raised alert level. Stations at ' + ', '.join(names) + ' should review their ashfall plans and watch PHIVOLCS bulletins.'
        else: todo = 'No action needed.'
        volcanoes.append(dict(id=v['id'], name=v['name'], lat=v['lat'], lon=v['lon'], x=x_, y=y_, onmap=(0 <= x_ <= 100 and 0 <= y_ <= 100), show=bool(v['main'] or v['erupt'] or (lvl or 0) >= 1),
            level=lvl, status=status, alert=alert, ms=v['ms'], title=v['name'] + ' Volcano',
            levelline=(f"Alert Level {lvl}. {LEVEL_WORDS[lvl]} ({v['level_asof']}.)" if lvl is not None else 'Alert level not available at this check. See the PHIVOLCS volcano bulletin for the current level.'),
            ashline=((' '.join(v['ash']) + ' ' + force[0].upper() + force[1:] + '.' + (f" The ash area covers {', '.join(v['hits'])}." if v['hits'] else ' No ash area covers an airport at this check.') +
                      ((f" Confirmed by Tokyo VAAC advisory {adv['nr']}, issued {clock(adv['dtg'])}." if adv and not byv else ('' if byv else (' Not yet confirmed by Tokyo VAAC.' if VAAC is not None else ' Tokyo VAAC could not be reached to confirm it.'))) + (' The aviation ash warning (SIGMET) has not been issued or could not be reached.' if byv else ''))) if v['erupt'] else 'No volcanic ash warning or advisory is in force for this volcano.'),
            near=neartxt, todo=todo,
            src=(('Ash and eruptions: ' + ' and '.join(([] if SIGMET is None else ['official aviation SIGMET (aviationweather.gov)']) + ([] if VAAC is None else ['Tokyo VAAC advisories (Japan Meteorological Agency)'])) + '. ') if vol_ok else 'Ash warnings could not be reached at this check. ') + ('Alert level: ' + v['level_asof'] + '.' if lvl is not None else 'Alert level: PHIVOLCS bulletin could not be read automatically.'),
            line=f"{v['name']}: " + (('eruption reported by Tokyo VAAC' if byv else 'eruption, ash warning in force') if v['erupt'] else (f'Alert Level {lvl}' if lvl is not None else 'no ash warning')) + '. ' + (f"Near {', '.join(names)}." if names else 'No airport within ' + str(VOLC_KM) + ' km.')))
    _rank = {'erupting': 0, 'high': 1, 'raised': 2, 'unrest': 3, 'unknown': 4, 'quiet': 5}
    volcanoes.sort(key=lambda v: (0 if v['alert'] else 1, _rank[v['status']], 0 if v['show'] else 1, v['name']))
    VOL_ALERTS.sort(key=lambda a: ({'ash': 0, 'eruption': 1, 'level': 2}[a['kind']], -a['ms']))
except Exception as _e:
    vol_ok = False; volcanoes = []; ASH_AREAS = []; VOL_ALERTS = []; print('VOLCANO ERROR', _e, file=sys.stderr)
# The two volcano sources, for the "data on screen now" boxes in the Help Centre.
try:
    _va_ok = SIGMET is not None
    _vaac_ok = VAAC is not None
    _used = ' and '.join((['Aviation ash warnings'] if _va_ok else []) + (['Tokyo VAAC'] if _vaac_ok else [])) or 'Not reached'
    SRC_STATUS.append(dict(what='Volcanic ash and eruptions', used=_used, ok=(_va_ok or _vaac_ok), first=_va_ok,
        chain=[dict(name='Aviation ash warnings, SIGMET (aviationweather.gov)', role='Primary. Gives the ash area', state=('used' if _va_ok else 'failed'), note=('Used' if _va_ok else 'Could not be reached'), tested=None),
               dict(name='Tokyo VAAC advisories (Japan Meteorological Agency)', role='Second source. Confirms, and stands in if the first is missing', state=('used' if _vaac_ok else 'failed'), note=('Used' if _vaac_ok else 'Could not be reached'), tested=None)]))
    _auto_ok = bool(locals().get('_auto')); _man_ok = bool(locals().get('_manual'))
    SRC_STATUS.append(dict(what='Volcano alert levels', used=('PHIVOLCS volcano bulletins' if _auto_ok else ('Levels entered by hand' if _man_ok else 'Not available at this check')), ok=True, first=_auto_ok,
        chain=[dict(name='PHIVOLCS volcano bulletins (wovodat.phivolcs.dost.gov.ph)', role='First choice', state=('used' if _auto_ok else 'failed'), note=('Used' if _auto_ok else 'Could not be read automatically'), tested=None),
               dict(name='Levels entered by hand (volcano_levels.json)', role=('Backup, in use' if (_man_ok and not _auto_ok) else ('Backup' if _man_ok else 'Backup. Nothing entered yet')), state=('used' if (_man_ok and not _auto_ok) else 'standby'), note=('Used' if (_man_ok and not _auto_ok) else ('Backup' if _man_ok else 'Backup, nothing entered')), tested=None)]))
except Exception as _e: print('VOLCANO SOURCE BOX ERROR', _e, file=sys.stderr)
_nerupt = sum(1 for v in volcanoes if v['status'] == 'erupting')
if not vol_ok: vol_flag = 'Volcanic ash warnings could not be reached at this check (neither the aviation warnings nor Tokyo VAAC).'
elif VOL_ALERTS: vol_flag = VOL_ALERTS[0]['text']
elif _nerupt: vol_flag = f"{_nerupt} volcano{'' if _nerupt == 1 else 'es'} with an ash warning in force; no airport is affected at this check."
else: vol_flag = 'No volcanic ash warning in the Philippine area, and no volcano alert for any airport.'
src.append(f"Volcanoes: ash clouds and eruptions are from official aviation ash warnings (SIGMET) on aviationweather.gov, checked {clock_plain(NOW)}. " + (f"Volcano alert levels are from {vol_level_src}." if vol_level_src else "Volcano alert levels could not be read automatically at this check; see PHIVOLCS volcano bulletins.") if vol_ok else "Volcanoes: the ash warning source could not be reached at this check.")

KEEP=('id','name','region','x','y','lat','lon','level','est','now','next','tmr','days','conf','todo','upd','src','what','when','sort','t','twhat','twhen','tsort','test','hours','estsrc','week')
QKEEP=('check','hits','ms','lat','lon','magnote','shocks','slist','nshock','id','mag','place','x','y','onmap','op','size','title','where','when','depth','near','tsu','after','todo','src','line')
data=dict(
    generated=NOW.strftime('%Y-%m-%dT%H:%M:%SZ'), generated_ms=int(NOW.timestamp()*1000), recent=RECENT,
    checked=' '.join(parts), problems=PROBLEMS,
    airports=[{k:r[k] for k in KEEP} for r in rows],
    quakes=[{k:q[k] for k in QKEEP} for q in quakes],
    quake_ok=bool(asof), flag=flag if asof else 'Earthquake data could not be reached at this check.',
    quake_asof=(f"{day(asof)}, {clock_plain(asof)}" if asof else ''),
    quake_count=(f"{len(quakes)} earthquake{'' if len(quakes)==1 else 's'} of magnitude 4.5+ in the past 7 days (purple rings, tap one for details). Small purple dots are aftershocks of a main earthquake." if asof else ''),
    ty_text=ty_main, ty_banner=ty_banner, ty_asof=((', '.join(k for k, ok in (('Aviation storm warnings', SIGMET is not None), ('RSMC Tokyo', JMATC is not None), ('GDACS', GDACS is not None)) if ok) + f", {day(NOW)}, {clock_plain(NOW)}") if tyok else ''),
    cyclones=CYCLONES, ty_alerts=TY_ALERTS, ty_near_km=TY_NEAR_KM,
    quake_src=QSRC, source_status=SRC_STATUS, eq_alerts=[dict(kind=a['kind'],q=a['q'],ms=a['ms'],text=a['text']) for a in EQ_ALERTS], rain_chance=bool(RAIN_CHANCE), week_ms=WEEK_MS, backup_tests=BACKUP_TESTS, thunder=dict(areas=TS_AREAS, airports=TS_AIRPORTS),
    tmr_note=f"{ph(T0).strftime('%A')}, {day(T0)}. Airports where bad weather is forecast for tomorrow, from airport forecasts and estimates. This is a forecast and is less certain than today's alerts. Select an airport on the map for its full report, including the days ahead.",
    volcanoes=volcanoes, vol_alerts=[dict(kind=a['kind'],key=a['key'],v=a['v'],ms=a['ms'],text=a['text']) for a in VOL_ALERTS], ash=ASH_AREAS, volcano_ok=vol_ok, volcano_flag=vol_flag,
    volcano_asof=((' and '.join(([] if SIGMET is None else ['Aviation ash warnings']) + ([] if VAAC is None else ['Tokyo VAAC'])) + f", {day(NOW)}, {clock_plain(NOW)}") if vol_ok else ''), volcano_km=VOLC_KM,
    sources=' '.join(src),
)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
tmp=OUT+'.tmp'
with open(tmp,'w',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,separators=(',',':'))
os.replace(tmp,OUT)
c=Counter(r['level'] for r in rows)
print(data['checked'])
print('Danger',c['danger'],'| Warning',c['warning'],'| Advisory',c['advisory'],'| Normal',c['normal'],'| No data',c['nodata'])
print(data['flag'])
for p in PROBLEMS: print('PROBLEM:',p)

# =====================================================================================
# RAIN AND THUNDER ANIMATION
# A grid of MET Norway forecasts over the map, hour by hour, saved as docs/rain.json.
# The page plays it as a moving rain layer. Rebuilt only every few hours, because the
# forecast itself changes only a few times a day and each rebuild needs many requests.
# =====================================================================================
RAIN_OUT = os.path.join(os.path.dirname(OUT), 'rain.json')
RAIN_EVERY_HOURS = 3          # how often to rebuild the animation
RAIN_HOURS = 30               # how many hours ahead to store
# The grid is much wider than the Philippines so the rain layer fills the whole map panel, even on
# very wide screens (the neighbouring countries are shown there as a picture). The middle part, over
# the Philippines, is read at every point. The outer parts are read at every second point and the
# points in between are filled in from their neighbours, which keeps the number of requests low.
GRID = dict(lat0=22.5, lon0=79.25, step=0.75, rows=26, cols=114)    # top-left point, spacing in degrees
GRID_FULL = (40, 73)          # first and last column read at every point (longitude 109.25 to 134)

def build_rain():
    try:
        with open(RAIN_OUT, encoding='utf-8') as f: old = json.load(f)
        age = (NOW.timestamp() * 1000 - old['generated_ms']) / 3.6e6
        if old.get('grid') != GRID: age = 1e9          # the grid was changed: rebuild now
    except Exception:
        age = 1e9
    if age < RAIN_EVERY_HOURS:
        print(f'Rain animation: still fresh ({age:.1f} hours old), not rebuilt.'); return
    from concurrent.futures import ThreadPoolExecutor
    allpts = [(r, c) for r in range(GRID['rows']) for c in range(GRID['cols'])]
    direct = lambda r, c: GRID_FULL[0] <= c <= GRID_FULL[1] or (r % 2 == 0 and c % 2 == 0)
    pts = [p for p in allpts if direct(*p)]
    h0 = NOW.replace(minute=0, second=0, microsecond=0)
    hours = [h0 + dt.timedelta(hours=i) for i in range(RAIN_HOURS)]
    def one(p):
        lat = GRID['lat0'] - p[0] * GRID['step']; lon = GRID['lon0'] + p[1] * GRID['step']
        m = fetch(f'https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat:.2f}&lon={lon:.2f}', tries=2, timeout=30)
        if not m: return None
        out = {}
        try:
            for e in m['properties']['timeseries']:
                n1 = e['data'].get('next_1_hours')
                if not n1: continue
                out[e['time'][:13]] = (float(n1['details'].get('precipitation_amount', 0.0) or 0.0), 'thunder' in (n1.get('summary', {}).get('symbol_code') or ''))
        except Exception:
            return None
        return out
    with ThreadPoolExecutor(max_workers=6) as ex: got = dict(zip(pts, ex.map(one, pts)))
    ok = sum(1 for r in got.values() if r)
    last_r = (GRID['rows'] - 1) // 2 * 2
    def near(r, c):
        # the points read directly that surround an outer point, with how much each one counts
        r0 = min(r - r % 2, last_r); r1 = min(r0 + 2, last_r); c0 = c - c % 2; c1 = c0 + 2
        if not (c1 < GRID['cols'] and direct(r0, c1)): c1 = c0
        fr = (r - r0) / 2.0 if r1 != r0 else 0.0; fc = (c - c0) / 2.0 if c1 != c0 else 0.0
        return [((r0, c0), (1 - fr) * (1 - fc)), ((r0, c1), (1 - fr) * fc), ((r1, c0), fr * (1 - fc)), ((r1, c1), fr * fc)]
    def value(p, k):
        if p in got:
            v = got[p].get(k) if got[p] else None
            return v if v else None
        tot = 0.0; wsum = 0.0
        for q, w in near(*p):
            v = got[q].get(k) if (w > 0 and got.get(q)) else None
            if v: tot += v[0] * w; wsum += w
        return (tot / wsum, False) if wsum > 0 else None
    if ok < 0.8 * len(pts):
        print(f'Rain animation: only {ok} of {len(pts)} grid points answered, keeping the previous animation.', file=sys.stderr); return
    rain = []; thunder = []
    for h in hours:
        k = h.strftime('%Y-%m-%dT%H'); fr = []; th = []
        for i, p in enumerate(allpts):
            v = value(p, k)
            fr.append(round(v[0], 1) if v else 0)
            if v and v[1]: th.append(i)
        rain.append(fr); thunder.append(th)
    doc = dict(generated_ms=int(NOW.timestamp() * 1000), source='MET Norway', grid=GRID, proj=P,
               times=[int(h.timestamp() * 1000) for h in hours], rain=rain, thunder=thunder)
    tmp = RAIN_OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f: json.dump(doc, f, separators=(',', ':'))
    os.replace(tmp, RAIN_OUT)
    print(f'Rain animation: rebuilt from {ok} of {len(pts)} grid points.')

# An urgent refresh for an earthquake or volcano alert skips the rain animation, which can take two minutes.
try:
    if os.environ.get('SKIP_RAIN') == '1': print('Rain animation: skipped for this urgent refresh.')
    else: build_rain()
except Exception as e: print('Rain animation could not be built:', e, file=sys.stderr)
