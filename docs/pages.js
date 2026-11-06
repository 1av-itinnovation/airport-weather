/* Shared helpers for the airport, event and report pages. View only: nothing here sends, saves or downloads. */
(function () {
  try {
    var p = localStorage.getItem('awm-theme') || 'auto';
    var dark = p === 'dark' || (p === 'auto' && window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  } catch (e) { document.documentElement.setAttribute('data-theme', 'light'); }
})();

var AW = {};
AW.TZ = 'Asia/Manila';
AW.LEVEL = { danger: 'Danger', warning: 'Warning', advisory: 'Advisory', normal: 'Normal', nodata: 'No data' };
AW.LRANK = { nodata: 0, normal: 1, advisory: 2, warning: 3, danger: 4 };
AW.HEAT = { caution: 'Caution', xcaution: 'Extreme caution', danger: 'Danger', xdanger: 'Extreme danger' };
AW.HEATRANGE = { caution: '27–32°C', xcaution: '33–41°C', danger: '42–51°C', xdanger: '52°C and above' };
AW.TOPIC = { flights: 'Flights and airport', typhoon: 'Typhoon', volcano: 'Volcano', quake: 'Earthquake', strike: 'Strike or protest', traffic: 'Traffic and roads', holiday: 'Holiday or event', power: 'Power', security: 'Security', weather: 'Weather' };
AW.IMPACT = { reported: 'Disruption reported', possible: 'Disruption possible', awareness: 'For awareness' };

AW.$ = function (id) { return document.getElementById(id); };
AW.esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
AW.param = function (k) { try { return new URLSearchParams(location.search).get(k); } catch (e) { return null; } };
AW.load = function (path) {
  return fetch(path + (path.indexOf('?') < 0 ? '?' : '&') + 't=' + Date.now(), { cache: 'no-store' }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
};
AW.loadOpt = function (path) { return AW.load(path).catch(function () { return null; }); };

function fmt(ms, o) { o.timeZone = AW.TZ; return new Intl.DateTimeFormat('en-US', o).format(new Date(ms)); }
AW.time = function (ms) { return fmt(ms, { hour: 'numeric', minute: '2-digit' }); };
AW.hour = function (ms) { return fmt(ms, { hour: 'numeric' }).replace(' ', ' '); };
AW.day = function (ms) { return fmt(ms, { weekday: 'short', month: 'short', day: 'numeric' }); };
AW.dayLong = function (ms) { return fmt(ms, { weekday: 'long', month: 'long', day: 'numeric' }); };
AW.stamp = function (ms) { return AW.day(ms) + ', ' + AW.time(ms); };
AW.ymd = function (ms) { return fmt(ms, { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/(\d+)\/(\d+)\/(\d+)/, '$3-$1-$2'); };
AW.ymdMs = function (s) { return Date.parse(s + 'T12:00:00+08:00'); };
AW.ago = function (ms) {
  var m = Math.round((Date.now() - ms) / 60000);
  if (m < 2) return 'just now'; if (m < 60) return m + ' minutes ago';
  var h = Math.round(m / 60); if (h < 24) return h + (h === 1 ? ' hour ago' : ' hours ago');
  var d = Math.round(h / 24); return d + (d === 1 ? ' day ago' : ' days ago');
};
AW.plural = function (n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); };
AW.list = function (a) { a = a.slice(); if (a.length < 2) return a.join(''); var l = a.pop(); return a.join(', ') + ' and ' + l; };
AW.pill = function (lv, txt) { return '<span class="pill ' + lv + '">' + AW.esc(txt || AW.LEVEL[lv] || lv) + '</span>'; };
AW.heatPill = function (lv, txt) { return '<span class="pill h-' + (lv || 'none') + '">' + AW.esc(txt || (lv ? 'Heat: ' + AW.HEAT[lv] : 'Heat: below caution')) + '</span>'; };
AW.km = function (a, b, c, d) {
  var R = 6371, r = Math.PI / 180, p1 = a * r, p2 = c * r, x = Math.pow(Math.sin((p2 - p1) / 2), 2) + Math.cos(p1) * Math.cos(p2) * Math.pow(Math.sin((d - b) * r / 2), 2);
  return 2 * R * Math.asin(Math.sqrt(x));
};
AW.short = function (name) { return String(name).replace(/ \(.*\)$/, ''); };
AW.apUrl = function (id) { return 'airport.html?id=' + encodeURIComponent(id); };
AW.evUrl = function (key) { return 'event.html?id=' + encodeURIComponent(key); };

/* page header: logo, breadcrumb, data time, and a way back. No share, copy or download controls. */
AW.header = function (crumbs, d, extra) {
  var c = '<a href="./">Dashboard</a>';
  crumbs.forEach(function (x, i) { c += '<span aria-hidden="true">›</span>' + (i === crumbs.length - 1 ? '<b>' + AW.esc(x) + '</b>' : '<span>' + AW.esc(x) + '</span>'); });
  var upd = d && d.generated_ms ? 'Updated ' + AW.stamp(d.generated_ms) + ' (Philippine time)' : '';
  return '<header class="top"><a href="./" aria-label="Back to the dashboard"><img class="logo" src="assets/logo-blue.png" alt="1Aviation"></a>' +
    '<nav aria-label="Breadcrumb">' + c + '</nav><div class="right">' + (extra || '') + (upd ? '<span class="upd">' + upd + '</span>' : '') +
    '<a class="btnlink ghost" href="./">Back to dashboard</a></div></header>';
};
AW.fail = function (el, msg) { el.innerHTML = '<div class="card empty">' + AW.esc(msg) + ' <a href="./">Back to the dashboard</a></div>'; };

/* Volcano "near" text: "Legazpi (Bicol) (about 20 km), Naga (about 60 km)." -> [{name, km}] */
AW.nearList = function (txt, d) {
  var out = [];
  (d.airports || []).forEach(function (a) {
    var i = (txt || '').indexOf(a.name + ' (about ');
    if (i < 0) return;
    var m = txt.slice(i + a.name.length).match(/^ \(about ([\d,]+) km\)/);
    out.push({ id: a.id, name: a.name, km: m ? +m[1].replace(/,/g, '') : null, pos: i });
  });
  return out.sort(function (a, b) { return a.pos - b.pos; });
};

/* Every hazard that touches an airport right now, strongest first. */
AW.hazardsFor = function (d, a) {
  var out = [];
  (d.volcanoes || []).forEach(function (v) {
    var lvl = +v.level || 0, ash = (v.hits || []).indexOf(a.name) >= 0, km = AW.km(v.lat, v.lon, a.lat, a.lon);
    if (!ash && !(km <= (d.volcano_km || 150) && (lvl >= 1 || v.eruptline))) return;
    var lv = ash ? 'danger' : (v.eruptline || lvl >= 3) ? 'warning' : 'advisory';
    out.push({ kind: 'volc', key: 'v:' + v.id, lv: lv, rank: AW.LRANK[lv], tag: lvl ? 'Level ' + lvl : 'Volcano', title: v.title,
      line: '<b>' + AW.esc(v.title) + (lvl ? ', Alert Level ' + lvl : '') + ', is about ' + Math.round(km / 10) * 10 + ' km away.</b> ' + AW.esc(ash ? 'Volcanic ash is forecast over this airport.' : v.ashline), todo: v.todo });
  });
  (d.cyclones || []).forEach(function (c) {
    var now = (c.now || []).indexOf(a.name) >= 0, soon = (c.soon || []).indexOf(a.name) >= 0;
    if (!c.show || !(now || soon)) return;
    out.push({ kind: 'typh', key: 't:' + c.id, lv: now ? 'danger' : 'warning', rank: now ? 4 : 3, tag: c.word || 'Typhoon', title: c.title,
      line: '<b>' + AW.esc(c.title) + (now ? ': strong winds can reach this airport now.' : ': strong winds can reach this airport within 24 hours.') + '</b> ' + AW.esc(c.where), todo: c.todo });
  });
  (d.quakes || []).forEach(function (q) {
    if ((q.hits || []).indexOf(a.name) < 0) return;
    out.push({ kind: 'quake', key: 'q:' + q.id, lv: 'warning', rank: 3, tag: 'M' + (+q.mag).toFixed(1), title: q.title,
      line: '<b>' + AW.esc(q.title) + '</b>, ' + AW.esc(q.where + ' ' + q.when), todo: q.todo });
  });
  return out.sort(function (x, y) { return y.rank - x.rank; });
};
AW.KINDPILL = { volc: 'volc', typh: 'typh', quake: 'quake' };
AW.KINDWORD = { volc: 'Volcano', typh: 'Typhoon', quake: 'Earthquake' };

/* Find an event from its key: v:<volcano>, t:<cyclone>, q:<quake>. A typhoon's id can change between
   checks, so a typhoon is also found by its name. */
AW.findEvent = function (d, key) {
  key = String(key || ''); var k = key.slice(0, 2), id = key.slice(2);
  if (k === 'v:') { var v = (d.volcanoes || []).filter(function (x) { return x.id === id; })[0]; return v ? { kind: 'volc', o: v, key: key } : null; }
  if (k === 't:') {
    var cs = d.cyclones || [], c = cs.filter(function (x) { return x.id === id; })[0];
    if (!c) { var nm = id.replace(/\d+$/, ''); c = cs.filter(function (x) { return x.show && x.id.replace(/\d+$/, '') === nm; })[0]; }
    return c ? { kind: 'typh', o: c, key: 't:' + c.id } : null;
  }
  if (k === 'q:') { var q = (d.quakes || []).filter(function (x) { return x.id === id || String(x.ms) === id; })[0]; return q ? { kind: 'quake', o: q, key: 'q:' + q.id } : null; }
  return null;
};
/* The events worth a page right now. */
AW.currentEvents = function (d) {
  var out = [];
  (d.volcanoes || []).forEach(function (v) { if (v.show && ((+v.level || 0) >= 1 || v.eruptline || (v.hits || []).length)) out.push({ kind: 'volc', key: 'v:' + v.id, title: v.title, sub: v.level ? 'Alert Level ' + v.level : 'Volcano', rank: (v.hits || []).length ? 9 : +v.level || 0, line: v.line }); });
  (d.cyclones || []).forEach(function (c) { if (c.show) out.push({ kind: 'typh', key: 't:' + c.id, title: c.title, sub: (c.now || []).length ? 'Strong winds reaching airports' : (c.soon || []).length ? 'Can reach airports within 24 hours' : 'No airport in reach', rank: (c.now || []).length ? 9 : (c.soon || []).length ? 6 : 1, line: c.where }); });
  (d.quakes || []).forEach(function (q) { if (q.onmap) out.push({ kind: 'quake', key: 'q:' + q.id, title: q.title, sub: q.place, rank: (q.hits || []).length ? 7 : 0.5, line: q.line, ms: q.ms }); });
  return out.sort(function (a, b) { return b.rank - a.rank; });
};

/* ---------- small map: the dashboard's Philippine map, zoomed to what matters ---------- */
// The map is a plain longitude/latitude grid: x% = 8.69278*lon - 1008.339, y% = -5.91775*lat + 125.458
AW.mapX = function (lon) { return 8.69278161 * lon - 1008.33883896; };
AW.mapY = function (lat) { return -5.91775171 * lat + 125.45788502; };
AW.ASPECT = 1506 / 1000;
AW.miniMap = function (el, o) {
  var pts = (o.fit || []).slice(), xs = pts.map(function (p) { return p.x; }), ys = pts.map(function (p) { return p.y; });
  var cx = (Math.min.apply(null, xs) + Math.max.apply(null, xs)) / 2, cy = (Math.min.apply(null, ys) + Math.max.apply(null, ys)) / 2;
  var spanX = Math.max(8, Math.max.apply(null, xs) - Math.min.apply(null, xs)), spanY = Math.max(5, Math.max.apply(null, ys) - Math.min.apply(null, ys));
  // container is 4:3; inner map is z times the container width.
  var z = Math.min(100 / (spanX * 1.35), 100 * 0.75 / (spanY * AW.ASPECT * 1.35));
  z = Math.max(0.45, Math.min(o.maxZoom || 7, z));
  var left = 50 - cx * z, top = 50 - (cy / 100) * z * AW.ASPECT / 0.75 * 100;
  var dark = document.documentElement.getAttribute('data-theme') === 'dark';
  var h = '<div class="mz" style="width:' + (z * 100) + '%;left:' + left + '%;top:' + top + '%"><img src="assets/' + (dark ? 'map-dark.svg' : 'map.svg') + '" alt="">';
  (o.rings || []).forEach(function (r) {
    var rx = r.km / (111.32 * Math.cos(r.lat * Math.PI / 180)) * 8.69278161, ry = r.km / 110.57 * 5.91775171;
    h += '<span class="ring ' + (r.cls || '') + '" style="left:' + r.x + '%;top:' + r.y + '%;width:' + (2 * rx) + '%;height:' + (2 * ry) + '%"></span>';
  });
  if (o.track && o.track.length > 1) {
    h += '<svg class="trk" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><polyline points="' + o.track.map(function (p) { return p.x + ',' + p.y; }).join(' ') +
      '" fill="none" stroke="var(--typh)" stroke-width="0.35" stroke-dasharray="1 0.8" vector-effect="non-scaling-stroke" style="stroke-width:2.5px"/></svg>';
  }
  (o.pins || []).forEach(function (p) {
    h += '<span class="p ' + (p.cls || '') + (p.x * z + left > 70 ? ' lft' : '') + '" style="left:' + p.x + '%;top:' + p.y + '%"><i style="background:' + (p.color || 'var(--accent)') + '"></i>' + (p.label ? '<span>' + AW.esc(p.label) + '</span>' : '') + '</span>';
  });
  el.innerHTML = '<div class="mm" role="img" aria-label="' + AW.esc(o.alt || 'Map') + '">' + h + '</div></div>';
};
AW.LVCOLOR = { danger: '#C62828', warning: '#F57C00', advisory: '#E0B800', normal: '#2E7D32', nodata: '#8A97AD' };

/* ---------- hover tip for charts ---------- */
AW.tip = (function () {
  var t = null;
  function show(html, x, y) {
    if (!t) { t = document.createElement('div'); t.className = 'tip'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.innerHTML = html; t.style.display = 'block';
    var w = t.offsetWidth, hh = t.offsetHeight, X = Math.min(window.innerWidth - w - 8, x + 14), Y = y - hh - 12 < 4 ? y + 18 : y - hh - 12;
    t.style.left = Math.max(8, X) + 'px'; t.style.top = Y + 'px';
  }
  function hide() { if (t) t.style.display = 'none'; }
  return { show: show, hide: hide };
})();

/* ---------- history ---------- */
AW.bits = function (n) { n = n || 0; var c = 0; while (n) { c += n & 1; n >>>= 1; } return c; };
AW.loadHistory = function (months) {
  return AW.loadOpt('history/index.json').then(function (ix) {
    var have = (ix && ix.months) || [];
    months = months.filter(function (m) { return have.indexOf(m) >= 0; });
    return Promise.all(months.map(function (m) { return AW.loadOpt('history/' + m + '.json'); })).then(function (xs) { return xs.filter(Boolean); });
  });
};
AW.monthsBack = function (ms, n) {
  var out = [], s = AW.ymd(ms), y = +s.slice(0, 4), m = +s.slice(5, 7);
  for (var i = 0; i < n; i++) { out.unshift(y + '-' + (m < 10 ? '0' : '') + m); m--; if (!m) { m = 12; y--; } }
  return out;
};
AW.monthName = function (ym) { return new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(+ym.slice(0, 4), +ym.slice(5, 7) - 1, 15))); };
