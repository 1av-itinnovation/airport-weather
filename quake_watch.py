#!/usr/bin/env python3
"""
Airport Weather Monitoring: fast earthquake and volcanic ash watch.

The full data refresh runs about every 20 minutes. This small check runs in between: every minute from the Live Alert
Watch (live_watch.py), and every few minutes on its own as a fallback.
It reads only the earthquake sources (PHIVOLCS first, then USGS) and the aviation ash warnings, and looks
for a strong earthquake or a volcanic ash warning that the dashboard does not show yet. If it finds one, it asks for a full refresh straight away, which updates
the dashboard and sends the Teams and email alert. If there is nothing new, it stops after a few seconds.

Developed by the 1AV IT Department. (c) 2026 1Aviation Groundhandling Services, Corp.
"""
import datetime as dt, json, os, re, ssl, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'docs', 'data.json')
STATE = os.path.join(HERE, 'notify_state.json')
MAX_TRIES = 2              # how many times one earthquake may ask for a full refresh (in case the first one fails)
WATCH_MAG = 5.0            # the smallest earthquake that can raise an alert
WATCH_HOURS = 3            # only look at earthquakes this recent
BOX = dict(minlat=3, maxlat=22, minlon=114, maxlon=130)     # the Philippine area, same as build.py
UA = '1AV-AirportWeatherDashboard/1.0 (earthquake watch)'
PHT = dt.timezone(dt.timedelta(hours=8))

def get(url, timeout=25, insecure_ok=False):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*'})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
    except Exception as e:
        if insecure_ok and 'CERTIFICATE' in str(e).upper(): r = urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())
        else: raise
    with r: return r.read().decode('utf-8', 'replace')

def phivolcs():
    html = get('https://earthquake.phivolcs.dost.gov.ph/', timeout=40, insecure_ok=True)
    txt = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', html, flags=re.S | re.I)
    txt = re.sub(r'<[^>]+>', ' ', txt).replace('&nbsp;', ' ').replace('&deg;', '°').replace('&#176;', '°')
    txt = ' '.join(re.sub(r'&[a-z#0-9]+;', ' ', txt).split())
    out = []
    for m in re.finditer(r'(\d{1,2}) ([A-Z][a-z]+) (\d{4}) - (\d{1,2}):(\d{2}) ([AP]M) (\d{1,2}\.\d+) (\d{2,3}\.\d+) (\d{1,3}) (\d\.\d) ', txt):
        try:
            hh = int(m.group(4)) % 12 + (12 if m.group(6) == 'PM' else 0)
            t = dt.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", '%d %B %Y').replace(hour=hh, minute=int(m.group(5)), tzinfo=PHT)
            out.append((int(t.timestamp() * 1000), float(m.group(7)), float(m.group(8)), float(m.group(10))))
        except Exception: continue
    if len(out) < 30: raise RuntimeError(f'PHIVOLCS page not read properly ({len(out)} rows)')
    return out

def usgs():
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=WATCH_HOURS)).strftime('%Y-%m-%dT%H:%M:%S')
    j = json.loads(get('https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=' + since + f"&minmagnitude={WATCH_MAG}"
                       f"&minlatitude={BOX['minlat']}&maxlatitude={BOX['maxlat']}&minlongitude={BOX['minlon']}&maxlongitude={BOX['maxlon']}"))
    return [(f['properties']['time'], f['geometry']['coordinates'][1], f['geometry']['coordinates'][0], float(f['properties']['mag'])) for f in j.get('features', []) if f['properties'].get('mag') is not None]

def ash_warnings():
    """Official volcanic ash warnings (SIGMET) now in force in the Philippine area: [(volcano name, start time in ms)]."""
    now = dt.datetime.now(dt.timezone.utc).timestamp(); out = []
    for x in json.loads(get('https://aviationweather.gov/api/data/isigmet?format=json&hazard=va', timeout=30)):
        if x.get('hazard') != 'VA' or not (x.get('validTimeFrom', 0) <= now + 3600 and x.get('validTimeTo', 0) > now): continue
        raw = ' '.join((x.get('rawSigmet') or '').split())
        if re.search(r'\bCNL\b|\bCANCEL', raw): continue
        cs = x.get('coords') or []; pts = []
        for pc in (cs if cs and isinstance(cs[0], list) else [cs]):
            pts += [(c['lat'], c['lon']) for c in pc if isinstance(c, dict) and c.get('lat') is not None and c.get('lon') is not None]
        if not (x.get('firId') == 'RPHI' or any(BOX['minlat'] <= la <= BOX['maxlat'] and BOX['minlon'] <= lo <= BOX['maxlon'] for la, lo in pts)): continue
        m = re.search(r'\bMT\.? ([A-Z][A-Z\' -]*?)(?= PSN| LOC| VA | OBS|$)', (x.get('qualifier') or '') + ' ' + raw)
        out.append((re.sub(r'[^a-z]', '', (m.group(1) if m else 'unnamed').lower()), int(x.get('validTimeFrom', 0)) * 1000))
    return out

def live_watch_running():
    """True when the Live Alert Watch (live-watch.yml) is running. It checks every minute, so this 5-minute check can stand down."""
    repo = os.environ.get('GITHUB_REPOSITORY'); tok = os.environ.get('GITHUB_TOKEN')
    if not repo or not tok: return False
    try:
        req = urllib.request.Request(f'https://api.github.com/repos/{repo}/actions/workflows/live-watch.yml/runs?status=in_progress&per_page=1',
                                     headers={'Authorization': 'Bearer ' + tok, 'Accept': 'application/vnd.github+json', 'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=15) as r: return json.load(r).get('total_count', 0) > 0
    except Exception as e:
        print(f'Could not ask whether the live watch is running ({type(e).__name__}); checking anyway.', file=sys.stderr); return False

def check(quiet=False):
    """Look once. Returns True when a full refresh is needed."""
    now = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    try: data = json.load(open(DATA, encoding='utf-8'))
    except Exception: data = {}
    known = [q.get('ms') for q in data.get('quakes', []) if q.get('ms')]
    found = []; reached = []
    for name, fn in (('PHIVOLCS', phivolcs), ('USGS', usgs)):
        try:
            for (ms, la, lo, mag) in fn():
                if mag < WATCH_MAG or not (0 <= now - ms <= WATCH_HOURS * 3600000): continue
                if not (BOX['minlat'] <= la <= BOX['maxlat'] and BOX['minlon'] <= lo <= BOX['maxlon']): continue
                if any(abs(ms - k) <= 5 * 60000 for k in known): continue           # the dashboard already shows it
                found.append((name, ms, mag))
            reached.append(name)
        except Exception as e:
            print(f'{name} not reached: {type(e).__name__}: {e}', file=sys.stderr)
    # volcanic ash: a warning for a volcano the dashboard is not yet showing as erupting
    ash_new = []
    try:
        shown = {re.sub(r'[^a-z]', '', v.get('name', '').lower()) for v in data.get('volcanoes', []) if v.get('status') == 'erupting'}
        for vname, ms in ash_warnings():
            if not any(vname == s_ or vname in s_ or s_ in vname for s_ in shown if s_): ash_new.append((vname, ms))
        reached.append('aviation ash warnings')
    except Exception as e:
        print(f'Ash warnings not reached: {type(e).__name__}: {e}', file=sys.stderr)
    for vname, ms in ash_new: print(f'NEW: volcanic ash warning ({vname})')
    for name, ms, mag in found:
        print(f"NEW: magnitude {mag:.1f} at {dt.datetime.fromtimestamp(ms / 1000, PHT).strftime('%b %d, %I:%M %p')} Philippine time ({name})")
    # do not keep asking for a refresh for the same earthquake (for example when the sources disagree about it)
    try: state = json.load(open(STATE, encoding='utf-8'))
    except Exception: state = {}
    tried = state.setdefault('watch', {}); need = False
    for name, ms, mag in found:
        key = str(round(ms / 600000))
        if tried.get(key, 0) < MAX_TRIES: tried[key] = tried.get(key, 0) + 1; need = True
    for vname, ms in ash_new:
        key = 'va:' + vname + ':' + str(round(ms / 3600000))
        if tried.get(key, 0) < MAX_TRIES: tried[key] = tried.get(key, 0) + 1; need = True
    for k in [k for k in tried if k.startswith('va:') and now - int(k.rsplit(':', 1)[1]) * 3600000 > 2 * 86400000]: del tried[k]
    for k in [k for k in tried if not k.startswith('va:') and now - int(k) * 600000 > 2 * 86400000]: del tried[k]
    if need: json.dump(state, open(STATE, 'w', encoding='utf-8'), separators=(',', ':'))
    if need or not quiet: print(f"Sources reached: {', '.join(reached) or 'none'}. " + ('Full refresh needed.' if need else 'Nothing new.'))
    return need

def main():
    if os.environ.get('WATCH_DEFER') == '1' and live_watch_running():
        print('The Live Alert Watch is running and checks every minute, so this check is not needed.'); need = False
    else:
        need = check()
    out = os.environ.get('GITHUB_OUTPUT')
    if out: open(out, 'a').write(f"refresh={'true' if need else 'false'}\n")

if __name__ == '__main__':
    main()
