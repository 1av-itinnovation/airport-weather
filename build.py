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

# ---------- earthquakes: every source is reshaped into the same layout ----------
def _feat(t, lat, lon, depth, mag, place, tsunami=None, felt=None, types=''):
    return {'properties': {'mag': mag, 'place': place, 'time': int(t.timestamp() * 1000), 'tsunami': tsunami, 'felt': felt, 'types': types},
            'geometry': {'coordinates': [lon, lat, depth]}}
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
                    found[p.get('eventid')] = dict(name='-'.join(w.capitalize() for w in name.split('-')), la=float(lat), lo=float(lon))
                except Exception: continue
        return {'gdacs': list(found.values())} if reached else None

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
SIGMET = _st.get('sigmet'); GDACS = _st.get('gdacs')
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
if SIGMET is None and GDACS is None: PROBLEMS.append(f"Typhoon data could not be reached ({_names('storms')}), so the typhoon watch is not available.")
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
try:
    Q=QUAKES
    if Q is None: raise RuntimeError('no earthquake source reached')
    asof=dt.datetime.fromtimestamp(Q['metadata']['generated']/1000,dt.timezone.utc)
    for f in sorted(Q['features'],key=lambda f:-f['properties']['time']):
        p=f['properties']; lo,la,dep=f['geometry']['coordinates']; t=dt.datetime.fromtimestamp(p['time']/1000,dt.timezone.utc)
        near=min(rows,key=lambda r:hav(la,lo,r['lat'],r['lon'])); dist=hav(la,lo,near['lat'],near['lon'])
        x=P['cx'][0]*lo+P['cx'][1]; y=P['cy'][0]*la+P['cy'][1]; recent=(NOW-t)<=dt.timedelta(hours=24)
        place=re.sub(r', Philippines$','',p['place'])
        dkm=int(round(dist/10)*10); hit=[]
        if recent and p['mag']>=5.0:
            for r in rows:
                dd=hav(la,lo,r['lat'],r['lon'])
                if dd<=100: flags.append((r['name'],p['mag'],round(dd),place,t)); hit.append(r['name'])
        dep=max(0,round(dep or 0)); dword='shallow' if dep<70 else 'mid-depth' if dep<300 else 'very deep'
        if hit: todo='Earthquake flag. Check runways, buildings and equipment at '+', '.join(hit)+' before normal work continues.'
        elif p['mag']<5.0: todo='No action needed. No airport flag: a flag needs magnitude 5.0 or stronger within 100 km of an airport in the last 24 hours.'
        elif not recent: todo='No action needed. This earthquake is more than 24 hours old and is shown for reference.'
        else: todo='No action needed. No airport is within 100 km of this earthquake.'
        quakes.append(dict(id=f'q{len(quakes)}',mag=p['mag'],place=place,x=x,y=y,onmap=(0<=x<=100 and 0<=y<=100),op=('1' if recent else '0.5'),size=round(14+(p['mag']-4.5)*16),
            title=f"Magnitude {p['mag']:.1f} earthquake",where=place+'.',when=f"{day(t)}, {clock_plain(t)} (Philippine time)."+(' Within the last 24 hours.' if recent else ''),
            depth=f"About {dep} km below ground ({dword}).",tsu=(f'{QSRC} has linked a tsunami notice to this earthquake. Check official tsunami bulletins for coastal airports.' if p.get('tsunami') else (f'No tsunami notice is linked to this earthquake ({QSRC}).' if p.get('tsunami') is False else f'{QSRC} data does not include tsunami notices. For a strong earthquake at sea, check PHIVOLCS tsunami bulletins.')),after=('USGS has published an aftershock forecast for this earthquake.' if 'oaf' in (p.get('types') or '') else 'Smaller earthquakes can follow in the same area over the next days. No official aftershock forecast has been published for this one.')+(f" {p['felt']} {'person' if p['felt']==1 else 'people'} reported feeling it to {QSRC}." if p.get('felt') else ''),near=f"{near['name']}, about {dkm} km away.",todo=todo,src=SOURCE_NAMES[USED['quakes']]+'.',
            line=f"{place}. {day(t)}, {clock_plain(t)}. Nearest airport: {near['name']}, about {dkm} km away."))
except Exception as e:
    qok=False; asof=None; quakes=[]; flags=[]; print('QUAKE ERROR',e,file=sys.stderr)
    if QUAKES is not None: PROBLEMS.append('Earthquake data could not be read.')
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
    if SIGMET is None and GDACS is None: raise RuntimeError('no typhoon source reached')
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
    for g in (GDACS or []):
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
T0=MIDNIGHT
for r in rows: r.pop('_area',None)
def common(ts): return Counter(ts).most_common(1)[0][0] if ts else None
ot=common(obs_times); tt=common(taf_times)
nOff=sum(1 for r in rows if not r['est'] and r['level']!='nodata'); nEst=sum(1 for r in rows if r['est'])
if est_times:
    e0=clock_plain(min(est_times)); e1=clock_plain(max(est_times)); et=e1 if e0==e1 else f'{e0} to {e1}'
else: et=None
n=ph(NOW)
parts=[f"Checked {n.strftime('%A')}, {day(NOW)}, {clock_plain(NOW)}."]
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
elif SIGMET is not None: src.append(f"Typhoon watch is from aviation storm warnings (SIGMET) on aviationweather.gov, checked {clock_plain(NOW)}; these look 6 hours ahead only.")
else: src.append(f"Typhoon watch is from the backup source GDACS, checked {clock_plain(NOW)}; it shows storm positions only.")
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
# Times of the most recent refreshes, so the page can learn how often the schedule really runs
# and show a realistic "next update" time (the hosting schedule often starts late).
try:
    with open(OUT, encoding='utf-8') as _f: _pd = json.load(_f)
    RECENT = [int(x) for x in (_pd.get('recent') or [])]
    if _pd.get('generated_ms') and int(_pd['generated_ms']) not in RECENT: RECENT.append(int(_pd['generated_ms']))
except Exception:
    RECENT = []
RECENT = sorted(set(RECENT + [int(NOW.timestamp()*1000)]))[-13:]
KEEP=('id','name','region','x','y','lat','lon','level','est','now','next','tmr','days','conf','todo','upd','src','what','when','sort','t','twhat','twhen','tsort','test','hours','estsrc')
QKEEP=('id','mag','place','x','y','onmap','op','size','title','where','when','depth','near','tsu','after','todo','src','line')
data=dict(
    generated=NOW.strftime('%Y-%m-%dT%H:%M:%SZ'), generated_ms=int(NOW.timestamp()*1000), recent=RECENT,
    checked=' '.join(parts), problems=PROBLEMS,
    airports=[{k:r[k] for k in KEEP} for r in rows],
    quakes=[{k:q[k] for k in QKEEP} for q in quakes],
    quake_ok=bool(asof), flag=flag if asof else 'Earthquake data could not be reached at this check.',
    quake_asof=(f"{day(asof)}, {clock_plain(asof)}" if asof else ''),
    quake_count=(f"{len(quakes)} earthquake{'' if len(quakes)==1 else 's'} of magnitude 4.5+ in the past 7 days (purple rings, tap one for details)." if asof else ''),
    ty_text=ty_main, ty_banner=ty_banner, ty_asof=(f"{'Aviation storm warnings' if SIGMET is not None else 'GDACS (backup source)'}, {day(NOW)}, {clock_plain(NOW)}" if tyok else ''),
    quake_src=QSRC, source_status=SRC_STATUS, rain_chance=bool(RAIN_CHANCE), backup_tests=BACKUP_TESTS, thunder=dict(areas=TS_AREAS, airports=TS_AIRPORTS),
    tmr_note=f"{ph(T0).strftime('%A')}, {day(T0)}. Airports where bad weather is forecast for tomorrow, from airport forecasts and estimates. This is a forecast and is less certain than today's alerts. Select an airport on the map for its full report, including the days ahead.",
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
# The grid is wider than the map image so the rain layer fills the whole map panel on wide screens.
GRID = dict(lat0=22.5, lon0=109.25, step=0.75, rows=26, cols=34)    # top-left point, spacing in degrees

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
    pts = [(r, c) for r in range(GRID['rows']) for c in range(GRID['cols'])]
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
    with ThreadPoolExecutor(max_workers=6) as ex: res = list(ex.map(one, pts))
    ok = sum(1 for r in res if r)
    if ok < 0.8 * len(pts):
        print(f'Rain animation: only {ok} of {len(pts)} grid points answered, keeping the previous animation.', file=sys.stderr); return
    rain = []; thunder = []
    for h in hours:
        k = h.strftime('%Y-%m-%dT%H'); fr = []; th = []
        for i, r in enumerate(res):
            v = r.get(k) if r else None
            fr.append(round(v[0], 1) if v else 0)
            if v and v[1]: th.append(i)
        rain.append(fr); thunder.append(th)
    doc = dict(generated_ms=int(NOW.timestamp() * 1000), source='MET Norway', grid=GRID, proj=P,
               times=[int(h.timestamp() * 1000) for h in hours], rain=rain, thunder=thunder)
    tmp = RAIN_OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f: json.dump(doc, f, separators=(',', ':'))
    os.replace(tmp, RAIN_OUT)
    print(f'Rain animation: rebuilt from {ok} of {len(pts)} grid points.')

try: build_rain()
except Exception as e: print('Rain animation could not be built:', e, file=sys.stderr)
