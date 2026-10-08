#!/usr/bin/env python3
"""
Airport Weather Monitoring: fast earthquake watch.

The full data refresh runs about every 20 minutes. This small check runs every few minutes in between.
It reads only the earthquake sources (PHIVOLCS first, then USGS) and looks for a strong earthquake that
the dashboard does not show yet. If it finds one, it asks for a full refresh straight away, which updates
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

def main():
    now = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    try: known = [q.get('ms') for q in json.load(open(DATA, encoding='utf-8')).get('quakes', []) if q.get('ms')]
    except Exception: known = []
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
    for name, ms, mag in found:
        print(f"NEW: magnitude {mag:.1f} at {dt.datetime.fromtimestamp(ms / 1000, PHT).strftime('%b %d, %I:%M %p')} Philippine time ({name})")
    # do not keep asking for a refresh for the same earthquake (for example when the sources disagree about it)
    try: state = json.load(open(STATE, encoding='utf-8'))
    except Exception: state = {}
    tried = state.setdefault('watch', {}); need = False
    for name, ms, mag in found:
        key = str(round(ms / 600000))
        if tried.get(key, 0) < MAX_TRIES: tried[key] = tried.get(key, 0) + 1; need = True
    for k in [k for k in tried if now - int(k) * 600000 > 2 * 86400000]: del tried[k]
    if need: json.dump(state, open(STATE, 'w', encoding='utf-8'), separators=(',', ':'))
    print(f"Sources reached: {', '.join(reached) or 'none'}. " + ('Full refresh needed.' if need else 'Nothing new.'))
    out = os.environ.get('GITHUB_OUTPUT')
    if out: open(out, 'a').write(f"refresh={'true' if need else 'false'}\n")

if __name__ == '__main__':
    main()
