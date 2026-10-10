#!/usr/bin/env python3
"""
Airport Weather Monitoring: the small map picture shown in Teams and email alerts.

Draws a zoomed map around the airport, earthquake or volcano an alert is about, in the dashboard's
style, and saves it under docs/alertmaps/ so the alert can show it. Only what the alert is about is
drawn: the airport itself, or the volcano with the airports named in the warning, or the earthquake
with its nearest airport.

Needs the Pillow library. If Pillow is missing, or anything here fails, the alert is simply sent
without a picture.

Developed by the 1AV IT Department. (c) 2026 1Aviation Groundhandling Services, Corp.
"""
import math, os, re, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, 'docs', 'alertmaps')
KEEP_DAYS = 7                     # old pictures are removed after this long
W, H, SS = 1040, 480, 2           # picture size, and how much larger it is drawn before being smoothed down
PROJ = dict(cx=(8.69278161, -1008.33883896), cy=(-5.91775171, 125.45788502))     # same map projection as the dashboard
LEVEL = {'danger': (198, 40, 40), 'warning': (245, 124, 0), 'advisory': (224, 174, 0), 'normal': (46, 125, 50)}
INK = (27, 43, 69); MUTED = (86, 101, 127); NAVY = (0, 86, 135); VOLC = (191, 54, 12); PURPLE = (106, 27, 154)

def ux(pct): return pct * 10.0                   # dashboard percent -> map units (the map drawing is 1000 x 1506)
def uy(pct): return pct * 15.06
def lon_x(lon): return ux(PROJ['cx'][0] * lon + PROJ['cx'][1])
def lat_y(lat): return uy(PROJ['cy'][0] * lat + PROJ['cy'][1])
KM_Y = PROJ['cy'][0] * -15.06 / 111.0            # map units per km, north-south
KM_X = lambda lat: PROJ['cx'][0] * 10.0 / (111.0 * max(0.2, math.cos(math.radians(lat))))

_MAP = None
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
    def card(self, x, y, title, sub, colour, icon):
        """The large name card, like the one beside a selected point on the dashboard. Goes right of the point, or left if there is no room."""
        fb = _font(self.s(24), True); fr = _font(self.s(18)); px, py = self.pt(x, y); s = self.s
        tw = max(self.d.textlength(title, font=fb), self.d.textlength(sub, font=fr) if sub else 0)
        w = s(64) + tw + s(30); h = s(72)
        left = px + s(34)
        if left + w > W * SS - s(10): left = px - s(34) - w
        left = max(s(10), left); top = min(max(py - h / 2, s(10)), H * SS - h - s(10))
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
        else:
            self.d.line([(cx - s(17), cy), (cx - s(9), cy), (cx - s(4), cy - s(14)), (cx + s(3), cy + s(14)), (cx + s(8), cy), (cx + s(17), cy)], fill=(255, 255, 255), width=s(3), joint='curve')
        self.d.text((left + s(74), top + (s(11) if sub else s(21))), title, font=fb, fill=INK)
        if sub: self.d.text((left + s(74), top + s(42)), sub, font=fr, fill=MUTED)
    def save(self, name):
        os.makedirs(OUT_DIR, exist_ok=True)
        out = self.im.resize((W, H), self.Image.LANCZOS)
        d = self.ImageDraw.Draw(out); d.rectangle([0, 0, W - 1, H - 1], outline=(202, 214, 221))
        out.save(os.path.join(OUT_DIR, name), optimize=True); return name

def airport_map(a):
    c = Canvas(ux(a['x']), uy(a['y']), 330)
    c.dot(ux(a['x']), uy(a['y']), LEVEL.get(a.get('level'), LEVEL['normal']), selected=True)
    c.card(ux(a['x']), uy(a['y']), a['name'], a.get('what') or '', LEVEL.get(a.get('level'), LEVEL['normal']), 'bolt')
    return c.save(name_for('danger', a))

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
    for ap in shown: c.tag(ux(ap['x']), uy(ap['y']), ap['name'], dx=-18 if ap['x'] < v['x'] else 18)
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
    span = 420
    if near: span = max(span, 2.6 * abs(ux(near['x']) - x) + 260, (2.6 * abs(uy(near['y']) - y) + 200) * W / H)
    c = Canvas(x, y, min(span, 900))
    r = max(18, (q.get('size') or 30)) * 1.1 / c.k * SS
    c.ring(x, y, r, r, PURPLE + (255,), dash=False, fill=(106, 27, 154, 46))
    px, py = c.pt(x, y); c.d.ellipse([px - c.s(5), py - c.s(5), px + c.s(5), py + c.s(5)], fill=PURPLE)
    if near:
        c.dot(ux(near['x']), uy(near['y']), LEVEL.get(near.get('level'), LEVEL['normal']))
        c.tag(ux(near['x']), uy(near['y']), near['name'], dx=-18 if near['x'] < q['x'] else 18)
    c.card(x, y, f"Magnitude {q['mag']:.1f} earthquake", re.sub(r'\s*\(.*$', '', str(q.get('place') or ''))[:44], PURPLE, 'quake')
    return c.save(name_for('quake', q))

def name_for(kind, obj):
    if kind == 'quake': return f"quake-{int(obj.get('ms') or 0)}.png"
    return f"{kind}-{re.sub(r'[^a-z0-9]', '', str(obj.get('id', '')).lower())}.png"

def render(kind, obj, data, alert=None):
    """Draw one picture. Returns its file name, or None if it could not be drawn."""
    try:
        if kind == 'danger': return airport_map(obj)
        if kind == 'volcano': return volcano_map(obj, alert or {}, data)
        if kind == 'quake' and obj.get('onmap', True): return quake_map(obj, data)
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
