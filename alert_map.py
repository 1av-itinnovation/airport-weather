#!/usr/bin/env python3
"""
Disruption Management Dashboard: the small map picture shown in Teams and email alerts.

Draws a zoomed map around the airport, earthquake or volcano an alert is about, in the dashboard's
style, and saves it under docs/alertmaps/ so the alert can show it. Only what the alert is about is
drawn: the airport itself, or the volcano with the airports named in the warning, or the earthquake
with its nearest airport.

Needs the Pillow library. If Pillow is missing, or anything here fails, the alert is simply sent
without a picture.

Developed by the 1AV IT Department. (c) 2026 1Aviation Groundhandling Services, Corp.
"""
import datetime as _dt, json, math, os, re, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, 'docs', 'alertmaps')
KEEP_DAYS = 7                     # old pictures are removed after this long
W, H, SS = 1040, 480, 2           # picture size, and how much larger it is drawn before being smoothed down
PROJ = dict(cx=(8.69278161, -1008.33883896), cy=(-5.91775171, 125.45788502))     # same map projection as the dashboard
LEVEL = {'danger': (198, 40, 40), 'warning': (245, 124, 0), 'advisory': (224, 174, 0), 'normal': (46, 125, 50)}
INK = (27, 43, 69); MUTED = (86, 101, 127); NAVY = (0, 86, 135); VOLC = (191, 54, 12); PURPLE = (106, 27, 154); TEAL = (11, 110, 138)

def ux(pct): return pct * 10.0                   # dashboard percent -> map units (the map drawing is 1000 x 1506)
def uy(pct): return pct * 15.06
def lon_x(lon): return ux(PROJ['cx'][0] * lon + PROJ['cx'][1])
def lat_y(lat): return uy(PROJ['cy'][0] * lat + PROJ['cy'][1])
KM_Y = PROJ['cy'][0] * -15.06 / 111.0            # map units per km, north-south
KM_X = lambda lat: PROJ['cx'][0] * 10.0 / (111.0 * max(0.2, math.cos(math.radians(lat))))

_MAP = None
def _runways():
    try: return json.load(open(os.path.join(HERE, 'runways.json'), encoding='utf-8'))
    except Exception: return {}
def _km_between(ax, ay, bx, by, lat):
    """Distance in km between two points given in map units."""
    return math.hypot((ax - bx) / KM_X(lat), (ay - by) / KM_Y)
def _km_text(d): return f"{int(round(d / 5.0) * 5) if d >= 10 else int(round(d))} km"
def _ph_time(ms):
    t = _dt.datetime.fromtimestamp(ms / 1000, _dt.timezone(_dt.timedelta(hours=8))); return t.strftime('%I:%M %p').lstrip('0')
def _load_map():
    """The coastlines from docs/assets/map.svg: [(fill, outline, [polygons])]."""
    global _MAP
    if _MAP is None:
        _MAP = []
        svg = open(os.path.join(HERE, 'docs', 'assets', 'map.svg'), encoding='utf-8').read()
        for m in re.finditer(r'<path d="([^"]*)"([^>]*)>', svg):
            ph = '#0077C8' in m.group(2)
            polys = []
            for part in m.group(1).split('M'):
                pts = [tuple(float(v) for v in xy.split(',')) for xy in part.replace('Z', ' ').split() if ',' in xy]
                if len(pts) >= 3: polys.append(pts)
            _MAP.append(((255, 255, 255) if ph else (238, 243, 244), (0, 119, 200) if ph else (195, 213, 218), 3 if ph else 2, polys))
    return _MAP

def _font(size, bold=False):
    from PIL import ImageFont
    for p in (('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf') if bold else
              ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/dejavu/DejaVuSans.ttf')):
        if os.path.exists(p): return ImageFont.truetype(p, size)
    try: return ImageFont.load_default(size=size)
    except TypeError: return ImageFont.load_default()

class Canvas:
    def __init__(self, cx, cy, span):
        """cx, cy: centre in map units. span: how many map units the picture is wide."""
        from PIL import Image, ImageDraw
        self.Image = Image; self.ImageDraw = ImageDraw
        self.k = W * SS / span; self.x0 = cx - span / 2; self.y0 = cy - span * H / W / 2
        self.im = Image.new('RGB', (W * SS, H * SS), (221, 238, 243)); self.d = ImageDraw.Draw(self.im, 'RGBA')
        for fill, line, lw, polys in _load_map():
            for pts in polys:
                q = [self.pt(x, y) for x, y in pts]
                xs = [a for a, _ in q]; ys = [b for _, b in q]
                if max(xs) < 0 or min(xs) > W * SS or max(ys) < 0 or min(ys) > H * SS: continue
                self.d.polygon(q, fill=fill); self.d.line(q + [q[0]], fill=line, width=lw * SS // 2 + 1)
    def pt(self, x, y): return ((x - self.x0) * self.k, (y - self.y0) * self.k)
    def s(self, v): return v * SS
    def dot(self, x, y, colour, selected=False):
        px, py = self.pt(x, y); s = self.s
        self.__dict__.setdefault('taken', []).append((px - s(13), py - s(13), px + s(13), py + s(13)))      # name tags keep clear of dots
        if selected: self.d.ellipse([px - s(21), py - s(21), px + s(21), py + s(21)], outline=NAVY + (255,), width=s(4), fill=(0, 86, 135, 30))
        self.d.ellipse([px - s(12), py - s(12), px + s(12), py + s(12)], fill=(255, 255, 255))
        self.d.ellipse([px - s(9), py - s(9), px + s(9), py + s(9)], fill=colour)
    def ring(self, x, y, rx, ry, colour, dash=True, fill=None):
        px, py = self.pt(x, y); rx *= self.k; ry *= self.k
        if fill: self.d.ellipse([px - rx, py - ry, px + rx, py + ry], fill=fill)
        n = 72
        for i in range(n):
            if dash and i % 2: continue
            a0 = 360.0 * i / n; self.d.arc([px - rx, py - ry, px + rx, py + ry], a0, a0 + 360.0 / n, fill=colour, width=self.s(3))
    def tag(self, x, y, text, dx=18, dy=0, colour=INK, bold=True, size=17):
        """A small rounded name tag beside a point. Takes the first spot that does not cover another tag."""
        f = _font(self.s(size), bold); px, py = self.pt(x, y); tw = self.d.textlength(text, font=f); s = self.s
        taken = self.__dict__.setdefault('taken', []); box = None
        for ddx, ddy in ((dx, dy), (-dx, dy), (dx, dy - 30), (dx, dy + 30), (-dx, dy - 30), (-dx, dy + 30)):
            left = px + s(ddx) if ddx >= 0 else px + s(ddx) - tw - s(20)
            left = min(max(left, s(8)), W * SS - tw - s(28)); top = min(max(py + s(ddy) - s(15), s(8)), H * SS - s(38))
            b = (left, top, left + tw + s(20), top + s(30))
            if box is None: box = b
            if not any(not (b[2] < t[0] or b[0] > t[2] or b[3] < t[1] or b[1] > t[3]) for t in taken): box = b; break
        taken.append(box)
        self.d.rounded_rectangle(list(box), radius=s(10), fill=(255, 255, 255, 235), outline=(190, 205, 220, 255), width=s(1))
        self.d.text((box[0] + s(10), box[1] + s(4)), text, font=f, fill=colour)
    def card(self, x, y, title, sub, colour, icon, avoid=None):
        """The large name card, like the one beside a selected point on the dashboard. Goes right of the point, or left if there is no room."""
        fb = _font(self.s(24), True); fr = _font(self.s(18)); px, py = self.pt(x, y); s = self.s
        tw = max(self.d.textlength(title, font=fb), self.d.textlength(sub, font=fr) if sub else 0)
        w = s(64) + tw + s(30); h = s(72)
        left = px + s(34)
        if left + w > W * SS - s(10): left = px - s(34) - w
        left = max(s(10), left); top = min(max(py - h / 2, s(10)), H * SS - h - s(10))
        if avoid is not None:      # a wide picture with many points: the card goes in whichever corner covers the fewest of them
            best = None
            for cl, ct in ((s(14), H * SS - h - s(14)), (W * SS - w - s(14), H * SS - h - s(14)), (s(14), s(14)), (W * SS - w - s(14), s(14))):
                n = sum(1 for ax, ay in avoid if cl - s(20) <= ax <= cl + w + s(20) and ct - s(20) <= ay <= ct + h + s(20))
                if best is None or n < best[0]: best = (n, cl, ct)
            left, top = best[1], best[2]
        self.d.rounded_rectangle([left + s(2), top + s(5), left + w + s(2), top + h + s(5)], radius=s(22), fill=(40, 60, 110, 46))
        self.d.rounded_rectangle([left, top, left + w, top + h], radius=s(22), fill=(255, 255, 255, 245))
        bx, by = left + s(10), top + s(10)
        self.d.rounded_rectangle([bx, by, bx + s(52), by + s(52)], radius=s(16), fill=colour)
        cx, cy = bx + s(26), by + s(26)
        if icon == 'bolt':
            shape = [(.56, 0), (.1, .58), (.44, .58), (.32, 1), (.9, .38), (.56, .38)]
            self.d.polygon([(cx + (a - .5) * s(26), cy + (b - .5) * s(32)) for a, b in shape], fill=(255, 255, 255))
        elif icon == 'volcano':
            self.d.polygon([(cx - s(15), cy + s(12)), (cx - s(5), cy - s(6)), (cx + s(5), cy - s(6)), (cx + s(15), cy + s(12))], outline=(255, 255, 255), width=s(3))
            for o in (-4, 4): self.d.line([(cx + s(o), cy - s(11)), (cx + s(o), cy - s(17))], fill=(255, 255, 255), width=s(3))
        elif icon == 'typhoon':
            self.d.ellipse([cx - s(7), cy - s(7), cx + s(7), cy + s(7)], outline=(255, 255, 255), width=s(3))
            self.d.arc([cx - s(4), cy - s(18), cx + s(26), cy + s(10)], 200, 290, fill=(255, 255, 255), width=s(3))
            self.d.arc([cx - s(26), cy - s(10), cx + s(4), cy + s(18)], 20, 110, fill=(255, 255, 255), width=s(3))
        else:
            self.d.line([(cx - s(17), cy), (cx - s(9), cy), (cx - s(4), cy - s(14)), (cx + s(3), cy + s(14)), (cx + s(8), cy), (cx + s(17), cy)], fill=(255, 255, 255), width=s(3), joint='curve')
        self.d.text((left + s(74), top + (s(11) if sub else s(21))), title, font=fb, fill=INK)
        if sub: self.d.text((left + s(74), top + s(42)), sub, font=fr, fill=MUTED)
    def dashed(self, pts, colour, width=2, on=12, off=8):
        """A dashed outline through points already in picture units."""
        s = self.s; pts = list(pts) + [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            L = math.hypot(x1 - x0, y1 - y0); n = max(1, int(L / s(on + off))); 
            for i in range(n + 1):
                a = i * s(on + off) / L if L else 0; b = min(1, a + s(on) / L) if L else 0
                if a >= 1: break
                self.d.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)], fill=colour, width=s(width))
    def arrow(self, a, b, colour, width=5):
        """An arrow between two points in picture units, with a white edge so it shows on any background."""
        s = self.s; ang = math.atan2(b[1] - a[1], b[0] - a[0]); hx, hy = math.cos(ang), math.sin(ang)
        base = (b[0] - hx * s(20), b[1] - hy * s(20)); head = [b, (base[0] - hy * s(11), base[1] + hx * s(11)), (base[0] + hy * s(11), base[1] - hx * s(11))]
        self.d.line([a, base], fill=(255, 255, 255, 255), width=s(width + 4)); self.d.polygon(head, fill=colour, outline=(255, 255, 255, 255))
        self.d.line([a, base], fill=colour, width=s(width)); self.d.polygon(head, fill=colour)
    def note(self, x, y, text, colour=INK, size=15, bold=True):
        """A tag centred on a point given in picture units (not moved to avoid others)."""
        f = _font(self.s(size), bold); s = self.s; tw = self.d.textlength(text, font=f)
        left = min(max(x - tw / 2 - s(9), s(6)), W * SS - tw - s(24)); top = min(max(y - s(14), s(6)), H * SS - s(34))
        box = (left, top, left + tw + s(18), top + s(28)); self.__dict__.setdefault('taken', []).append(box)
        self.d.rounded_rectangle(list(box), radius=s(9), fill=(255, 255, 255, 240), outline=colour + (150,), width=s(1))
        self.d.text((left + s(9), top + s(4)), text, font=f, fill=colour)
    def save(self, name):
        os.makedirs(OUT_DIR, exist_ok=True)
        out = self.im.resize((W, H), self.Image.LANCZOS)
        d = self.ImageDraw.Draw(out); d.rectangle([0, 0, W - 1, H - 1], outline=(202, 214, 221))
        out.save(os.path.join(OUT_DIR, name), optimize=True); return name

def airport_map(a):
    c = Canvas(ux(a['x']), uy(a['y']), 330)
    c.dot(ux(a['x']), uy(a['y']), LEVEL.get(a.get('level'), LEVEL['normal']), selected=True)
    c.card(ux(a['x']), uy(a['y']), a['name'], a.get('what') or '', LEVEL.get(a.get('level'), LEVEL['normal']), 'bolt')
    try: _airport_inset(c, a)
    except Exception as e: print('Alert map: the airport close-up could not be drawn:', type(e).__name__, e)
    return c.save(name_for('danger', a))

def _airport_inset(c, a):
    """The same close-up the dashboard shows: the runway at its true direction, the wind arrow, and rings at 5 km and 10 km."""
    R = _runways().get(a.get('id')) or []; o = a.get('obs') or {}
    if not R: return
    s = c.s; d = c.d; bw, bh = s(330), s(300); left, top = s(16), H * SS - bh - s(16)
    d.rounded_rectangle([left + s(2), top + s(4), left + bw + s(2), top + bh + s(4)], radius=s(18), fill=(40, 60, 110, 40))
    d.rounded_rectangle([left, top, left + bw, top + bh], radius=s(18), fill=(255, 255, 255, 248))
    d.text((left + s(16), top + s(10)), 'Airport close-up', font=_font(s(17), True), fill=INK)
    px0, py0, px1, py1 = left + s(12), top + s(40), left + bw - s(12), top + bh - s(66)
    d.rounded_rectangle([px0, py0, px1, py1], radius=s(10), fill=(237, 243, 247, 255))
    cx, cy = (px0 + px1) / 2, (py0 + py1) / 2; K = s(13.5)                    # picture units for one km
    clip = c.Image.new('L', c.im.size, 0); cd = c.ImageDraw.Draw(clip); cd.rounded_rectangle([px0, py0, px1, py1], radius=s(10), fill=255)
    lay = c.Image.new('RGBA', c.im.size, (0, 0, 0, 0)); ld = c.ImageDraw.Draw(lay)
    ld.ellipse([cx - 5 * K, cy - 5 * K, cx + 5 * K, cy + 5 * K], fill=(198, 40, 40, 16))
    for km, alpha in ((5, 255), (10, 150)):
        n = 60
        for i in range(0, n, 2): ld.arc([cx - km * K, cy - km * K, cx + km * K, cy + km * K], 360.0 * i / n, 360.0 * (i + 1) / n, fill=(198, 40, 40, alpha), width=s(2))
    f = _font(s(13), True)
    for rw in R:
        ax, ay, bx, by = cx + rw[3] * K, cy - rw[4] * K, cx + rw[5] * K, cy - rw[6] * K
        ld.line([(ax, ay), (bx, by)], fill=(42, 52, 69, 255), width=s(6))
        L = math.hypot(bx - ax, by - ay) or 1; uxx, uyy = (bx - ax) / L, (by - ay) / L
        for (tx, ty), nm in (((ax - uxx * s(15), ay - uyy * s(15)), rw[0]), ((bx + uxx * s(15), by + uyy * s(15)), rw[1])):
            tw = ld.textlength(nm, font=f); ld.text((tx - tw / 2, ty - s(9)), nm, font=f, fill=INK + (255,))
    c.im.paste(c.Image.alpha_composite(c.im.convert('RGBA'), lay).convert('RGB'), (0, 0), clip); c.d = d = c.ImageDraw.Draw(c.im, 'RGBA')
    d.text((cx - d.textlength('5 km', font=_font(s(12), True)) / 2, cy - 5 * K - s(17)), '5 km', font=_font(s(12), True), fill=MUTED)
    d.text((px1 - s(44), py1 - s(20)), '10 km', font=_font(s(12), True), fill=MUTED)
    d.polygon([(px1 - s(18), py0 + s(8)), (px1 - s(13), py0 + s(22)), (px1 - s(23), py0 + s(22))], fill=MUTED); d.text((px1 - s(23), py0 + s(23)), 'N', font=_font(s(12), True), fill=MUTED)
    if not o.get('est') and o.get('wd') is not None and o.get('w'):
        wx, wy = math.sin(math.radians(o['wd'])), -math.cos(math.radians(o['wd']))
        c.arrow((cx + wx * s(96), cy + wy * s(96)), (cx + wx * s(48), cy + wy * s(48)), (0, 119, 200), width=4)
    xl = str(o.get('xline') or ''); m = re.match(r'(\d+) km/h across runway (\S+), with a (headwind|tailwind) of (\d+) km/h', xl)
    wind = ('Calm, no wind' if not (o.get('w') or o.get('g')) else f"Wind {o.get('w')} km/h" + (f", gusts {o['g']}" if o.get('g') else '')) if (o and not o.get('est')) else 'No official wind report'
    if m: big, small = f"Crosswind {m.group(1)} km/h", f"runway {m.group(2)}, {m.group(3)} {m.group(4)} km/h. {wind}"
    else: big, small = 'Runway ' + ' and '.join(r_[0] + '/' + r_[1] for r_ in R), wind
    d.text((left + s(16), top + bh - s(58)), big, font=_font(s(18), True), fill=INK); d.text((left + s(16), top + bh - s(32)), small, font=_font(s(13)), fill=MUTED)

def volcano_map(v, alert, data):
    km = data.get('volcano_km') or 150
    x, y = ux(v['x']), uy(v['y'])
    c = Canvas(x, y, 2 * km * KM_Y * 1.22 * W / H)
    for ash in data.get('ash') or []:
        if ash.get('v') in (v.get('id'), None) and len(ash.get('p') or []) >= 3:
            q = [c.pt(ux(p[0]), uy(p[1])) for p in ash['p']]
            c.d.polygon(q, fill=(93, 64, 55, 80)); c.d.line(q + [q[0]], fill=(78, 52, 46, 255), width=c.s(2))
    c.ring(x, y, km * KM_X(v.get('lat', 12)), km * KM_Y, VOLC + (220,), fill=(191, 54, 12, 14))
    c.tag(x, y + km * KM_Y, f'{km} km from the volcano', dx=-0, dy=0, colour=VOLC, size=15)
    # only the airports named in the warning; for an eruption or level alert, the nearest one
    named = [n.strip() for n in str(alert.get('key', '')).split(':', 2)[2].split(',')] if alert.get('kind') == 'ash' and str(alert.get('key', '')).count(':') >= 2 else []
    if not named and v.get('near'): named = [re.sub(r'\s*\(about.*$', '', str(v['near']).split('), ')[0]).strip()]
    shown = [ap for ap in data.get('airports', []) if ap['name'] in named]
    for ap in shown: c.dot(ux(ap['x']), uy(ap['y']), LEVEL.get(ap.get('level'), LEVEL['normal']))
    BROWN = (78, 52, 46)
    for fc in data.get('ash_fc') or []:      # where Tokyo VAAC expects the ash in the coming hours
        if fc.get('v') == v.get('id') and len(fc.get('p') or []) >= 3:
            q = [c.pt(ux(p[0]), uy(p[1])) for p in fc['p']]
            c.d.polygon(q, fill=(93, 64, 55, 22)); c.dashed(q, BROWN + (255,), width=2)
            far = max(q, key=lambda t: math.hypot(t[0] - c.pt(x, y)[0], t[1] - c.pt(x, y)[1]))
            if fc.get('ms'): c.note(far[0], far[1], 'By ' + _ph_time(fc['ms']), colour=BROWN, size=13)
    mv = v.get('mv') or {}
    if mv.get('deg') is not None:            # which way the ash is moving: from the volcano through the ash cloud
        dxm, dym = math.sin(math.radians(mv['deg'])), -math.cos(math.radians(mv['deg'])); L = 0
        for ash in data.get('ash') or []:
            if ash.get('v') == v.get('id'):
                for p in ash.get('p') or []: L = max(L, (ux(p[0]) - x) * dxm + (uy(p[1]) - y) * dym)
        L = max(L + 14, 46); c.arrow(c.pt(x, y), c.pt(x + dxm * L, y + dym * L), (62, 39, 35))
    for ap in shown: c.tag(ux(ap['x']), uy(ap['y']), ap['name'] + ', ' + _km_text(_km_between(ux(ap['x']), uy(ap['y']), x, y, v.get('lat', 12))), dx=-18 if ap['x'] < v['x'] else 18)
    hm = re.search(r'up to about ([\d,]+ m)', str(v.get('ashline') or ''))
    if mv.get('word') or hm:
        tops = [uy(p[1]) for ash in data.get('ash') or [] if ash.get('v') == v.get('id') for p in ash.get('p') or []]
        nx, ny = c.pt(x, min(tops) if tops else y - km * KM_Y * 0.5)
        c.note(nx, ny - c.s(20), 'Ash cloud' + (', up to ' + hm.group(1) if hm else '') + (', moving ' + mv['word'] if mv.get('word') else ''), colour=BROWN, size=14)
    px, py = c.pt(x, y); s = c.s
    c.d.ellipse([px - s(22), py - s(22), px + s(22), py + s(22)], outline=VOLC + (255,), width=s(4), fill=(191, 54, 12, 40))
    c.d.polygon([(px, py - s(11)), (px - s(11), py + s(8)), (px + s(11), py + s(8))], fill=VOLC, outline=(255, 255, 255))
    sub = {'ash': 'Volcanic ash warning', 'eruption': 'Eruption', 'level': f"Alert Level {v.get('level')}"}.get(alert.get('kind'), '')
    c.card(x, y, v.get('title') or v.get('name', 'Volcano'), sub, VOLC, 'volcano')
    return c.save(name_for('volcano', v))

def quake_map(q, data):
    x, y = ux(q['x']), uy(q['y'])
    near = None; nm = re.sub(r',.*$', '', str(q.get('near') or '')).strip()
    for ap in data.get('airports', []):
        if ap['name'] == nm: near = ap
    lat = q.get('lat', 12); span = max(420, 2 * 100 * KM_Y * 1.16 * W / H)      # wide enough for the whole 100 km ring
    if near: span = max(span, 2.6 * abs(ux(near['x']) - x) + 260, (2.6 * abs(uy(near['y']) - y) + 200) * W / H)
    c = Canvas(x, y, min(span, 900))
    for km_, a_ in ((100, 200), (50, 150), (25, 150)):      # the same distance rings as the dashboard
        c.ring(x, y, km_ * KM_X(lat), km_ * KM_Y, PURPLE + (a_,))
        ex, ey = c.pt(x, y + km_ * KM_Y); c.note(ex, ey, f'{km_} km', colour=PURPLE, size=12)
    within = [ap for ap in data.get('airports', []) if _km_between(ux(ap['x']), uy(ap['y']), x, y, lat) <= 100 and ap is not near]
    r = max(18, (q.get('size') or 30)) * 1.1 / c.k * SS
    c.ring(x, y, r, r, PURPLE + (255,), dash=False, fill=(106, 27, 154, 46))
    px, py = c.pt(x, y); c.d.ellipse([px - c.s(5), py - c.s(5), px + c.s(5), py + c.s(5)], fill=PURPLE)
    if near:
        c.dot(ux(near['x']), uy(near['y']), LEVEL.get(near.get('level'), LEVEL['normal']))
    for ap in within: c.dot(ux(ap['x']), uy(ap['y']), LEVEL.get(ap.get('level'), LEVEL['normal']))
    for ap in ([near] if near else []) + within[:8]:
        c.tag(ux(ap['x']), uy(ap['y']), ap['name'] + ', ' + _km_text(_km_between(ux(ap['x']), uy(ap['y']), x, y, lat)), dx=-18 if ap['x'] < q['x'] else 18)
    c.card(x, y, f"Magnitude {q['mag']:.1f} earthquake", re.sub(r'\s*\(.*$', '', str(q.get('place') or ''))[:44], PURPLE, 'quake')
    return c.save(name_for('quake', q))

def typhoon_map(t, alert, data):
    """The cyclone, how far its strong winds reach, where it is forecast to be in 24 hours, and the airports the alert names."""
    x, y = ux(t['x']), uy(t['y'])
    km = t.get('reach') or t.get('gale') or data.get('ty_near_km') or 300
    named = (t.get('now') if alert.get('kind') != 'soon' else t.get('soon')) or t.get('now') or t.get('soon') or []
    shown = [ap for ap in data.get('airports', []) if ap['name'] in named]
    pts = [(x, y)] + [(ux(ap['x']), uy(ap['y'])) for ap in shown]
    if t.get('fx') is not None and t.get('fy') is not None: pts.append((ux(t['fx']), uy(t['fy'])))
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts); y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    span = max((x1 - x0) + 420, ((y1 - y0) + 260) * W / H, 700)
    c = Canvas((x0 + x1) / 2, (y0 + y1) / 2, min(span, 2600))
    c.ring(x, y, km * KM_X(t.get('lat', 12)), km * KM_Y, TEAL + (230,), fill=(11, 110, 138, 18))
    if t.get('storm') and t['storm'] < km:      # the inner ring of storm-force winds, when RSMC Tokyo reports it
        c.ring(x, y, t['storm'] * KM_X(t.get('lat', 12)), t['storm'] * KM_Y, (198, 40, 40, 235), dash=False, fill=(198, 40, 40, 22))
    if t.get('fx') is not None and t.get('fy') is not None:
        fx, fy = ux(t['fx']), uy(t['fy']); a = c.pt(x, y); b = c.pt(fx, fy); n = 14
        for i in range(0, n, 2):
            c.d.line([(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n), (a[0] + (b[0] - a[0]) * (i + 1) / n, a[1] + (b[1] - a[1]) * (i + 1) / n)], fill=TEAL + (255,), width=c.s(3))
        c.d.ellipse([b[0] - c.s(9), b[1] - c.s(9), b[0] + c.s(9), b[1] + c.s(9)], fill=(255, 255, 255, 240), outline=TEAL + (255,), width=c.s(3))
        c.__dict__.setdefault('taken', []).append((b[0] - c.s(12), b[1] - c.s(12), b[0] + c.s(12), b[1] + c.s(12)))
    for ap in shown: c.dot(ux(ap['x']), uy(ap['y']), LEVEL.get(ap.get('level'), LEVEL['normal']))
    px, py = c.pt(x, y); s = c.s
    c.__dict__.setdefault('taken', []).append((px - s(26), py - s(26), px + s(26), py + s(26)))
    c.__dict__['taken'].append((0, 0, 0, 0))
    for ap in shown[:10]: c.tag(ux(ap['x']), uy(ap['y']), ap['name'] + (', now' if ap['name'] in (t.get('now') or []) else ', within 24 h' if ap['name'] in (t.get('soon') or []) else ''), dx=-18 if ap['x'] < t['x'] else 18, size=15)
    if t.get('fx') is not None and t.get('fy') is not None: c.tag(ux(t['fx']), uy(t['fy']), 'In 24 hours', dx=16, dy=-30, colour=TEAL, size=14)
    if t.get('storm') and t['storm'] < km:
        sx_, sy_ = c.pt(x, y - t['storm'] * KM_Y); c.note(sx_, sy_ - c.s(4), f"Storm-force winds, {int(round(t['storm'] / 10.0) * 10)} km", colour=(183, 28, 28), size=13)
    c.d.ellipse([px - s(22), py - s(22), px + s(22), py + s(22)], outline=TEAL + (255,), width=s(4), fill=(255, 255, 255, 235))
    c.d.ellipse([px - s(8), py - s(8), px + s(8), py + s(8)], fill=TEAL)
    c.d.arc([px - s(5), py - s(19), px + s(27), py + s(11)], 205, 285, fill=TEAL, width=s(3)); c.d.arc([px - s(27), py - s(11), px + s(5), py + s(19)], 25, 105, fill=TEAL, width=s(3))
    c.card(x, y, t.get('title') or 'Tropical cyclone', (f"Winds {t['wind']} km/h" if t.get('wind') else '') + (f", strong winds reach about {int(round(km / 10.0) * 10)} km" if t.get('gale') else ''), TEAL, 'typhoon', avoid=[c.pt(*p) for p in pts])
    return c.save(name_for('typhoon', t))

def name_for(kind, obj):
    if kind == 'quake': return f"quake-{int(obj.get('ms') or 0)}.png"
    if kind == 'typhoon': return f"typhoon-{re.sub(r'[^a-z0-9]', '', str(obj.get('name') or obj.get('id', '')).lower())}.png"
    return f"{kind}-{re.sub(r'[^a-z0-9]', '', str(obj.get('id', '')).lower())}.png"

def render(kind, obj, data, alert=None):
    """Draw one picture. Returns its file name, or None if it could not be drawn."""
    try:
        if kind == 'danger': return airport_map(obj)
        if kind == 'volcano': return volcano_map(obj, alert or {}, data)
        if kind == 'quake' and obj.get('onmap', True): return quake_map(obj, data)
        if kind == 'typhoon': return typhoon_map(obj, alert or {}, data)
    except ImportError:
        print('Alert map: Pillow is not installed, so the alert goes without a picture.')
    except Exception as e:
        print('Alert map could not be drawn:', type(e).__name__, e)
    return None

def tidy():
    """Remove pictures older than KEEP_DAYS."""
    try:
        for f in os.listdir(OUT_DIR):
            p = os.path.join(OUT_DIR, f)
            if f.endswith('.png') and time.time() - os.path.getmtime(p) > KEEP_DAYS * 86400: os.remove(p)
    except Exception: pass
