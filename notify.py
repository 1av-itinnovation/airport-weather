#!/usr/bin/env python3
"""
Airport Weather Monitoring: email notifications.

Runs straight after build.py. Reads docs/data.json and sends ONE email when there is something new:
  * an earthquake alert (strong earthquake, earthquake near an airport, possible tsunami), or
  * an airport that has just gone to Danger (thunderstorm at the airport, official report).

It remembers what it has already sent in notify_state.json, so the same alert is never emailed twice.

Settings come from the repository's secrets (Settings > Secrets and variables > Actions), never from
this file, because this repository is public:
  SMTP_HOST   mail server, for example smtp.office365.com
  SMTP_PORT   usually 587
  SMTP_USER   the mailbox that sends the email
  SMTP_PASS   its password or app password
  MAIL_TO     who receives it; several addresses separated by commas
  MAIL_FROM   optional; defaults to SMTP_USER
If SMTP_HOST or MAIL_TO is missing, nothing is sent and the refresh carries on as normal.

Instead of a mail server, the alert can be handed to a Power Automate flow, which sends it from Outlook:
  ALERT_WEBHOOK_URL   the address of the flow's "When a Teams webhook request is received" trigger
When this is set it is used, and the SMTP settings are ignored. The flow receives subject, html, text, teams (short message), card (a Teams card) and tier (alert, headsup or briefing).

Developed by the 1AV IT Department. (c) 2026 1Aviation Groundhandling Services, Corp.
"""
import datetime as dt, html, json, os, smtplib, ssl, sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'docs', 'data.json')
STATE = os.path.join(HERE, 'notify_state.json')

DANGER_REPEAT_HOURS = 3      # an airport that leaves Danger and returns is emailed again only after this long
QUAKE_MAX_AGE_HOURS = 6      # do not email about an earthquake older than this (for example on the very first run)
KEEP_DAYS = 3                # how long sent-alert records are kept
# Only the most critical messages are sent: an airport at Danger, an earthquake alert, a possible tsunami.
# The two optional kinds below are switched off. Change False to True to switch one on.
SEND_HEADSUP = False         # advance notice: thunderstorm expected within the hour, typhoon entering the area
SEND_BRIEFING = False        # the whole picture at fixed times each day
HEADSUP_REPEAT_HOURS = 3     # an airport is not put in a second heads-up within this long
BRIEF_HOURS = (5, 13)        # daily briefing times, Philippine time (24-hour clock): 5:00 AM and 1:00 PM
CARD_ROWS_TODAY = 18; CARD_ROWS_TOMORROW = 8     # Teams cards have a size limit, so long lists are cut short there (the email shows all)
BRIEF_WINDOW_HOURS = 2       # a briefing is sent at the first refresh in this window after its time, never later

PHT = dt.timezone(dt.timedelta(hours=8))
def pht(ms): return dt.datetime.fromtimestamp(ms / 1000, PHT)
def clock(ms): t = pht(ms); return f"{t.strftime('%b')} {t.day}, {t.strftime('%I:%M %p').lstrip('0')}"
def esc(s): return html.escape(str(s or ''))

def dashboard_url():
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    if '/' in repo:
        owner, name = repo.split('/', 1); return f"https://{owner.lower()}.github.io/{name}/"
    return os.environ.get('DASHBOARD_URL', '')

# ---------- what is new ----------
def find_new(d, state, now_ms):
    sent = state.setdefault('sent', {}); danger_now = state.setdefault('danger', {})
    quakes = {q['id']: q for q in d.get('quakes', [])}
    new_q = []; new_d = []
    for a in d.get('eq_alerts', []):
        ms = a.get('ms') or 0
        key = f"eq:{a['kind']}:{round(ms / 600000)}"            # same earthquake = same 10-minute slot
        if key in sent: continue
        sent[key] = now_ms
        if ms and now_ms - ms > QUAKE_MAX_AGE_HOURS * 3600000: continue
        new_q.append((a, quakes.get(a.get('q'))))
    current = {a['id']: a for a in d.get('airports', []) if a.get('level') == 'danger'}
    for aid, a in current.items():
        last = danger_now.get(aid)
        if last is None and now_ms - sent.get('dg:' + aid, 0) > DANGER_REPEAT_HOURS * 3600000:
            new_d.append(a); sent['dg:' + aid] = now_ms
        danger_now.setdefault(aid, now_ms)          # kept unchanged while it stays at Danger, so the record is not rewritten every run
    for aid in [k for k in danger_now if k not in current]: del danger_now[aid]
    for k in [k for k, v in sent.items() if now_ms - v > KEEP_DAYS * 86400000]: del sent[k]
    return new_q, new_d

# ---------- the email ----------
NAVY = '#005687'; BLUE = '#0077C8'; TINT = '#CAE2E7'; INK = '#12303F'; MUTED = '#5B7180'; RED = '#C62828'; PURPLE = '#6A1B9A'; DARKRED = '#7F1D1D'
FONT = "font-family:'Segoe UI',Arial,Helvetica,sans-serif"

def row(label, value):
    if not value: return ''
    return (f'<tr><td style="padding:7px 0;border-top:1px solid #E6EEF1;{FONT};font-size:12px;color:{MUTED};width:132px;vertical-align:top">{esc(label)}</td>'
            f'<td style="padding:7px 0 7px 10px;border-top:1px solid #E6EEF1;{FONT};font-size:13.5px;line-height:1.5;color:{INK};vertical-align:top">{esc(value)}</td></tr>')

def card(colour, tag, title, rows, action):
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 16px;border:1px solid #DCE7EB;border-left:5px solid {colour};border-radius:6px;background:#FFFFFF">'
            f'<tr><td style="padding:16px 18px 14px">'
            f'<span style="display:inline-block;background:{colour};color:#FFFFFF;{FONT};font-size:11px;font-weight:700;letter-spacing:.06em;padding:3px 8px;border-radius:4px;text-transform:uppercase">{esc(tag)}</span>'
            f'<div style="{FONT};font-size:18px;font-weight:600;color:{INK};margin:9px 0 10px;line-height:1.3">{esc(title)}</div>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'
            + (f'<div style="margin-top:12px;background:#F3F8FA;border-radius:5px;padding:10px 12px;{FONT};font-size:13.5px;line-height:1.5;color:{INK}"><strong>What to do.</strong> {esc(action)}</div>' if action else '')
            + '</td></tr></table>')

def build_email(d, new_q, new_d):
    url = dashboard_url(); cards = []; text = []; subj = []
    for a, q in new_q:
        tsu = a['kind'] == 'tsunami'
        if q:
            title = f"Magnitude {q['mag']:.1f} earthquake"
            when = f"{clock(q['ms'])} (Philippine time)" if q.get('ms') else q.get('when')
            rows = [row('Time it happened', when), row('Where', q.get('where')), row('Magnitude', q.get('magnote') or f"{q['mag']:.1f}"), row('Depth', q.get('depth')),
                    row('Nearest airport', q.get('near')), row('Tsunami', q.get('tsu')), row('Aftershocks', q.get('after')), row('Source', q.get('src'))]
            action = q.get('todo'); place = q.get('place', '')
            nearname = (q.get('near') or '').split(',')[0].strip()
            subj.append(('Possible tsunami, ' if tsu else 'Earthquake ') + f"M{q['mag']:.1f}" + (f" near {nearname}" if nearname else ''))
            text.append(f"{'POSSIBLE TSUNAMI' if tsu else 'EARTHQUAKE'}: {title}\nTime it happened: {when}\nWhere: {q.get('where')}\nMagnitude: {q.get('magnote') or q['mag']}\nNearest airport: {q.get('near')}\nTsunami: {q.get('tsu')}\nWhat to do: {action}\n")
        else:
            title = 'Possible tsunami' if tsu else 'Earthquake alert'; rows = [row('Details', a['text'])]; action = ''
            subj.append(title); text.append(a['text'] + '\n')
        cards.append(card(DARKRED if tsu else PURPLE, 'Possible tsunami' if tsu else 'Earthquake', title, rows, action))
    for a in new_d:
        rows = [row('Right now', a.get('now')), row('Rest of today', a.get('next')), row('Confidence', a.get('conf')), row('Updated', a.get('upd')), row('Source', a.get('src'))]
        cards.append(card(RED, 'Danger', a['name'], rows, a.get('todo')))
        text.append(f"DANGER: {a['name']}\nRight now: {a.get('now')}\nRest of today: {a.get('next')}\nWhat to do: {a.get('todo')}\nUpdated: {a.get('upd')}\n")
    if new_d: subj.append('Danger: ' + (', '.join(a['name'] for a in new_d) if len(new_d) <= 2 else f'{len(new_d)} airports'))
    subject = 'Airport Weather: ' + ' | '.join(subj)
    if len(subject) > 90: subject = subject[:87] + '...'
    checked = (d.get('checked') or '').split('. ')[0].rstrip('.')
    n = len(new_q) + len(new_d)
    intro = ('A new alert has been raised on the Airport Weather Monitoring dashboard.' if n == 1 else f'{n} new alerts have been raised on the Airport Weather Monitoring dashboard.')
    button = (f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:4px 0 6px"><tr><td style="background:{BLUE};border-radius:5px">'
              f'<a href="{esc(url)}" style="display:inline-block;padding:10px 20px;{FONT};font-size:14px;font-weight:600;color:#FFFFFF;text-decoration:none">Open the dashboard</a></td></tr></table>') if url else ''
    body = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(subject)}</title></head>
<body style="margin:0;padding:0;background:#F3F7F9">
<div style="display:none;max-height:0;overflow:hidden;color:#F3F7F9">{esc(' | '.join(subj))}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F3F7F9"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px">
<tr><td style="background:{NAVY};border-radius:8px 8px 0 0;padding:18px 24px">
<div style="{FONT};font-size:18px;font-weight:600;color:#FFFFFF">Airport Weather Monitoring</div>
<div style="{FONT};font-size:12.5px;color:{TINT};margin-top:3px">Alert notification &middot; {esc(checked)} (Philippine time)</div></td></tr>
<tr><td style="background:#FFFFFF;padding:22px 24px 8px;border-left:1px solid #DCE7EB;border-right:1px solid #DCE7EB">
<div style="{FONT};font-size:14px;line-height:1.55;color:{INK};margin:0 0 16px">{esc(intro)}</div>
{''.join(cards)}
{button}
</td></tr>
<tr><td style="background:#FFFFFF;border:1px solid #DCE7EB;border-top:none;border-radius:0 0 8px 8px;padding:14px 24px 20px">
<div style="{FONT};font-size:11.5px;line-height:1.55;color:{MUTED};border-top:1px solid #E6EEF1;padding-top:12px">
Developed by the 1AV IT Department. &copy; 2026 1Aviation Groundhandling Services, Corp.</div></td></tr>
</table></td></tr></table></body></html>"""
    plain = intro + '\n\n' + '\n'.join(text) + (f'\nDashboard: {url}\n' if url else '') + '\nAutomatic message from Airport Weather Monitoring. Developed by the 1AV IT Department.'
    return subject, plain, body

def teams_text(new_q, new_d):
    """A short version for a Teams channel message."""
    out = []
    for a, q in new_q:
        if q: out.append(f"<b>{'Possible tsunami' if a['kind'] == 'tsunami' else 'Earthquake'}: magnitude {q['mag']:.1f}</b>, {esc(q.get('place'))}<br>Happened: {esc(clock(q['ms']) if q.get('ms') else q.get('when'))} (Philippine time)<br>Nearest airport: {esc(q.get('near'))}<br>What to do: {esc(q.get('todo'))}")
        else: out.append(esc(a.get('text')))
    for a in new_d:
        out.append(f"<b>Danger: {esc(a['name'])}</b><br>{esc(a.get('now'))}<br>What to do: {esc(a.get('todo'))}")
    url = dashboard_url()
    return '<br><br>'.join(out) + (f'<br><br><a href="{esc(url)}">Open the dashboard</a>' if url else '')

def teams_card(d, new_q, new_d, test=False):
    """The alert as a Teams card (Adaptive Card), in the dashboard's colours: navy header with the logo, then one
    block per alert with a coloured rule and tag (purple = earthquake, red = Danger), and a button to the dashboard.
    Teams cards cannot take custom colours directly, so small pictures in docs/assets (card-*.png) supply the
    navy header, the coloured rule above each alert and the coloured tags. If those files are missing, the card falls back to Teams' own colours."""
    url = dashboard_url()
    have = bool(url) and all(os.path.exists(os.path.join(HERE, 'docs', 'assets', f'card-{c}.png')) for c in ('navy', 'bar-purple', 'bar-red', 'bar-darkred', 'tag-earthquake', 'tag-danger', 'tag-tsunami', 'button'))
    def bg(c): return {'url': f'{url}assets/card-{c}.png', 'fillMode': 'Repeat'}
    def tb(text, **kw): return dict({'type': 'TextBlock', 'text': str(text or ''), 'wrap': True}, **kw)
    def line(label, value):
        return {'type': 'ColumnSet', 'spacing': 'Small', 'columns': [
            {'type': 'Column', 'width': '120px', 'items': [tb(label, size='Small', isSubtle=True)]},
            {'type': 'Column', 'width': 'stretch', 'items': [tb(value)]}]}
    def block(colour, fallback, tag, title, pairs, action):
        key = {'Earthquake': 'earthquake', 'Danger': 'danger', 'Possible tsunami': 'tsunami'}[tag]
        if have:
            top = [{'type': 'Image', 'url': f'{url}assets/card-bar-{colour}.png', 'size': 'Stretch', 'altText': ''},
                   {'type': 'Image', 'url': f'{url}assets/card-tag-{key}.png', 'height': '22px', 'altText': tag, 'spacing': 'Medium'}]
        else:
            top = [tb(tag.upper(), size='Small', weight='Bolder', color=fallback)]
        items = top + [tb(title, size='Large', weight='Bolder', spacing='Small')] + [line(k, v) for k, v in pairs if v]
        if action: items.append({'type': 'Container', 'style': 'emphasis', 'spacing': 'Medium', 'items': [tb('**What to do.** ' + action)]})
        return {'type': 'Container', 'spacing': 'Large', 'separator': not have, 'items': items}
    checked = (d.get('checked') or '').split('. ')[0].rstrip('.')
    n = len(new_q) + len(new_d)
    head = [tb('Airport Weather Monitoring', size='Large', weight='Bolder', color='Light' if have else 'Default'),
            tb(f'Alert notification \u00b7 {checked} (Philippine time)', size='Small', spacing='None', color='Light' if have else 'Default', isSubtle=not have)]
    if have:
        header = {'type': 'Container', 'bleed': True, 'backgroundImage': bg('navy'), 'items': [{'type': 'ColumnSet', 'columns': [
            {'type': 'Column', 'width': 'auto', 'verticalContentAlignment': 'Center', 'items': [{'type': 'Image', 'url': f'{url}assets/logo.png', 'height': '30px', 'altText': '1Aviation'}]},
            {'type': 'Column', 'width': 'stretch', 'verticalContentAlignment': 'Center', 'items': head}]}]}
    else:
        header = {'type': 'Container', 'style': 'accent', 'bleed': True, 'items': head}
    body = [header]
    if test: body.append({'type': 'Container', 'style': 'warning', 'items': [tb('**THIS IS A TEST.** It uses what is on the dashboard now. It is not a new alert.', size='Small')]})
    body.append(tb('A new alert has been raised on the dashboard.' if n == 1 else f'{n} new alerts have been raised on the dashboard.'))
    for a, q in new_q:
        tsu = a['kind'] == 'tsunami'; colour = 'darkred' if tsu else 'purple'; tag = 'Possible tsunami' if tsu else 'Earthquake'
        if q:
            when = f"{clock(q['ms'])} (Philippine time)" if q.get('ms') else q.get('when')
            body.append(block(colour, 'Attention' if tsu else 'Accent', tag, f"Magnitude {q['mag']:.1f} earthquake",
                [('Time it happened', when), ('Where', q.get('where')), ('Magnitude', q.get('magnote') or f"{q['mag']:.1f}"), ('Depth', q.get('depth')), ('Nearest airport', q.get('near')),
                 ('Tsunami', q.get('tsu')), ('Aftershocks', q.get('after')), ('Source', q.get('src'))], q.get('todo')))
        else:
            body.append(block(colour, 'Attention' if tsu else 'Accent', tag, 'Earthquake alert', [('Details', a.get('text'))], ''))
    for a in new_d:
        body.append(block('red', 'Attention', 'Danger', a['name'], [('Right now', a.get('now')), ('Rest of today', a.get('next')), ('Confidence', a.get('conf')), ('Updated', a.get('upd')), ('Source', a.get('src'))], a.get('todo')))
    card = {'type': 'AdaptiveCard', '$schema': 'http://adaptivecards.io/schemas/adaptive-card.json', 'version': '1.4', 'msteams': {'width': 'Full'}, 'body': body}
    if url and have:        # a picture of a button in the dashboard's blue, because Teams draws its own buttons in its own colours
        body.append({'type': 'Image', 'url': f'{url}assets/card-button.png', 'height': '36px', 'altText': 'Open the dashboard', 'spacing': 'Large',
                     'selectAction': {'type': 'Action.OpenUrl', 'title': 'Open the dashboard', 'url': url}})
    elif url: card['actions'] = [{'type': 'Action.OpenUrl', 'title': 'Open the dashboard', 'url': url, 'style': 'positive'}]
    return json.dumps(card, ensure_ascii=False)

def fragment(body):
    """The email design as a plain block of tables, for mail systems that reject a whole web page
    (Power Automate's Outlook step drops the content when it is given a full page with its own head and body)."""
    import re
    i = body.find('<table'); j = body.rfind('</table>')
    f = body[i:j + 8] if i >= 0 and j > i else body
    f = f.replace(' role="presentation"', '')
    def bg(m):                                   # older mail programs only honour the bgcolor attribute
        tag, rest = m.group(1), m.group(2)
        c = re.search(r'background:(#[0-9A-Fa-f]{6})', rest)
        return f'<{tag} bgcolor="{c.group(1)}"{rest}>' if c and 'bgcolor=' not in rest else m.group(0)
    f = re.sub(r'<(table|td)((?:\s[^>]*)?)>', bg, f)
    return ' '.join(f.split())

def send_webhook(subject, plain, body, teams, card='', tier='alert'):
    """Hand the email to a Power Automate flow, which sends it from Outlook (and can post to Teams)."""
    import urllib.request
    url = os.environ.get('ALERT_WEBHOOK_URL', '').strip()
    if not url: return False
    payload = json.dumps({'subject': subject, 'html': fragment(body), 'text': plain, 'teams': teams, 'card': card, 'tier': tier, 'dashboard': dashboard_url()}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f'Alert handed to the Power Automate flow (reply {r.status}): {subject}')
    return True

def deliver(subject, plain, body, teams='', card='', tier='alert'):
    """Power Automate flow if ALERT_WEBHOOK_URL is set, otherwise the mail server."""
    if os.environ.get('ALERT_WEBHOOK_URL', '').strip(): return send_webhook(subject, plain, body, teams, card, tier)
    return send(subject, plain, body)

def send(subject, plain, body):
    host = os.environ.get('SMTP_HOST', '').strip(); to = [x.strip() for x in os.environ.get('MAIL_TO', '').replace(';', ',').split(',') if x.strip()]
    if not host or not to:
        print('Email not set up (SMTP_HOST or MAIL_TO missing); nothing sent.'); return False
    user = os.environ.get('SMTP_USER', '').strip(); pw = os.environ.get('SMTP_PASS', ''); port = int(os.environ.get('SMTP_PORT') or 587)
    sender = os.environ.get('MAIL_FROM', '').strip() or user
    m = EmailMessage(); m['Subject'] = subject; m['From'] = f'Airport Weather Monitoring <{sender}>'; m['To'] = ', '.join(to)
    m['Date'] = formatdate(localtime=False); m['Message-ID'] = make_msgid(); m['X-Priority'] = '2'; m['Importance'] = 'High'
    m.set_content(plain); m.add_alternative(body, subtype='html')
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
            if user: s.login(user, pw)
            s.send_message(m)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.ehlo(); s.starttls(context=ctx); s.ehlo()
            if user: s.login(user, pw)
            s.send_message(m)
    print(f'Email sent to {len(to)} recipient(s): {subject}'); return True

# =====================================================================================
# HEADS-UP (advance notice) and DAILY BRIEFING
# Alert    : something is happening now (Danger airport, earthquake, possible tsunami).  Sent at once.
# Heads-up : a thunderstorm is expected at an airport within the hour, or a typhoon has entered the
#            Philippine area. All new ones from one refresh go out together as ONE message.
# Briefing : the whole picture, at fixed times each day (BRIEF_HOURS).
# =====================================================================================
AMBER = '#F57C00'; YELLOW = '#B58900'
LEVEL_NAME = {'danger': 'Danger', 'warning': 'Warning', 'advisory': 'Advisory'}
LEVEL_HEX = {'danger': RED, 'warning': AMBER, 'advisory': YELLOW}

def typhoon_active(d): return bool(d.get('ty_banner')) and not str(d['ty_banner']).lower().startswith('no typhoon')

def find_headsup(d, state, now_ms):
    """Airports that have just moved to Warning because of a thunderstorm, and a typhoon newly in the area."""
    sent = state.setdefault('sent', {}); cur_w = state.setdefault('warn', {})
    now_set = {a['id']: a for a in d.get('airports', []) if a.get('level') == 'warning' and 'thunderstorm' in str(a.get('what', '')).lower()}
    out = []
    for aid, a in now_set.items():
        if aid not in cur_w and now_ms - sent.get('hu:' + aid, 0) > HEADSUP_REPEAT_HOURS * 3600000:
            out.append(a); sent['hu:' + aid] = now_ms
        cur_w.setdefault(aid, now_ms)
    for aid in [k for k in cur_w if k not in now_set]: del cur_w[aid]
    ty = typhoon_active(d); new_ty = ty and not state.get('ty')
    state['ty'] = bool(ty)
    return sorted(out, key=lambda a: a['name']), new_ty

def brief_slot(state, now_ms):
    """Returns the briefing that is due now ('2026-10-09-5'), or None."""
    t = pht(now_ms)
    for h in BRIEF_HOURS:
        if h <= t.hour < h + BRIEF_WINDOW_HOURS:
            key = f"{t.strftime('%Y-%m-%d')}-{h}"
            if key not in state.setdefault('briefs', []): return key
    return None

def _table(headers, rows_, widths):
    th = ''.join(f'<td style="padding:6px 8px 6px 0;{FONT};font-size:11.5px;color:{MUTED};width:{w}">{esc(h)}</td>' for h, w in zip(headers, widths))
    body = ''
    for r in rows_:
        body += '<tr>' + ''.join(f'<td style="padding:7px 8px 7px 0;border-top:1px solid #E6EEF1;{FONT};font-size:13px;line-height:1.45;color:{INK};vertical-align:top">{c}</td>' for c in r) + '</tr>'
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{th}</tr>{body}</table>'

def _section(colour, tag, title, inner, note=''):
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 16px;border:1px solid #DCE7EB;border-left:5px solid {colour};border-radius:6px;background:#FFFFFF"><tr><td style="padding:16px 18px 14px">'
            + (f'<span style="display:inline-block;background:{colour};color:#FFFFFF;{FONT};font-size:11px;font-weight:700;letter-spacing:.06em;padding:3px 8px;border-radius:4px;text-transform:uppercase">{esc(tag)}</span>' if tag else '')
            + f'<div style="{FONT};font-size:17px;font-weight:600;color:{INK};margin:{"9px" if tag else "0"} 0 8px;line-height:1.3">{esc(title)}</div>{inner}'
            + (f'<div style="margin-top:12px;background:#F3F8FA;border-radius:5px;padding:10px 12px;{FONT};font-size:13.5px;line-height:1.5;color:{INK}">{note}</div>' if note else '')
            + '</td></tr></table>')

def _shell(d, subject, kicker, intro, inner):
    """The email frame shared by heads-ups and briefings (same look as the alert email)."""
    url = dashboard_url(); checked = (d.get('checked') or '').split('. ')[0].rstrip('.')
    button = (f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:4px 0 6px"><tr><td style="background:{BLUE};border-radius:5px">'
              f'<a href="{esc(url)}" style="display:inline-block;padding:10px 20px;{FONT};font-size:14px;font-weight:600;color:#FFFFFF;text-decoration:none">Open the dashboard</a></td></tr></table>') if url else ''
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(subject)}</title></head>
<body style="margin:0;padding:0;background:#F3F7F9">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F3F7F9"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px">
<tr><td style="background:{NAVY};border-radius:8px 8px 0 0;padding:18px 24px">
<div style="{FONT};font-size:18px;font-weight:600;color:#FFFFFF">Airport Weather Monitoring</div>
<div style="{FONT};font-size:12.5px;color:{TINT};margin-top:3px">{esc(kicker)} &middot; {esc(checked)} (Philippine time)</div></td></tr>
<tr><td style="background:#FFFFFF;padding:22px 24px 8px;border-left:1px solid #DCE7EB;border-right:1px solid #DCE7EB">
<div style="{FONT};font-size:14px;line-height:1.55;color:{INK};margin:0 0 16px">{esc(intro)}</div>
{inner}
{button}
</td></tr>
<tr><td style="background:#FFFFFF;border:1px solid #DCE7EB;border-top:none;border-radius:0 0 8px 8px;padding:14px 24px 20px">
<div style="{FONT};font-size:11.5px;line-height:1.55;color:{MUTED};border-top:1px solid #E6EEF1;padding-top:12px">
Developed by the 1AV IT Department. &copy; 2026 1Aviation Groundhandling Services, Corp.</div></td></tr>
</table></td></tr></table></body></html>"""

# ----- Teams card pieces shared by heads-ups and briefings -----
def _tb(text, **kw): return dict({'type': 'TextBlock', 'text': str(text or ''), 'wrap': True}, **kw)
def _cols(cells, widths, **kw):
    return dict({'type': 'ColumnSet', 'spacing': 'Small', 'columns': [{'type': 'Column', 'width': w, 'items': [c if isinstance(c, dict) else _tb(c)]} for c, w in zip(cells, widths)]}, **kw)
def _have(names):
    url = dashboard_url()
    return bool(url) and all(os.path.exists(os.path.join(HERE, 'docs', 'assets', f'card-{n}.png')) for n in names)
def _card(d, kicker, intro, blocks, test=False):
    url = dashboard_url(); have = _have(('navy', 'button')); checked = (d.get('checked') or '').split('. ')[0].rstrip('.')
    head = [_tb('Airport Weather Monitoring', size='Large', weight='Bolder', color='Light' if have else 'Default'),
            _tb(f'{kicker} · {checked} (Philippine time)', size='Small', spacing='None', color='Light' if have else 'Default', isSubtle=not have)]
    if have:
        header = {'type': 'Container', 'bleed': True, 'backgroundImage': {'url': f'{url}assets/card-navy.png', 'fillMode': 'Repeat'}, 'items': [{'type': 'ColumnSet', 'columns': [
            {'type': 'Column', 'width': 'auto', 'verticalContentAlignment': 'Center', 'items': [{'type': 'Image', 'url': f'{url}assets/logo.png', 'height': '30px', 'altText': '1Aviation'}]},
            {'type': 'Column', 'width': 'stretch', 'verticalContentAlignment': 'Center', 'items': head}]}]}
    else:
        header = {'type': 'Container', 'style': 'accent', 'bleed': True, 'items': head}
    body = [header]
    if test: body.append({'type': 'Container', 'style': 'warning', 'items': [_tb('**THIS IS A TEST.** It uses what is on the dashboard now. It is not a new message.', size='Small')]})
    body.append(_tb(intro)); body += blocks
    card = {'type': 'AdaptiveCard', '$schema': 'http://adaptivecards.io/schemas/adaptive-card.json', 'version': '1.4', 'msteams': {'width': 'Full'}, 'body': body}
    if url and have:
        body.append({'type': 'Image', 'url': f'{url}assets/card-button.png', 'height': '36px', 'altText': 'Open the dashboard', 'spacing': 'Large', 'selectAction': {'type': 'Action.OpenUrl', 'title': 'Open the dashboard', 'url': url}})
    elif url: card['actions'] = [{'type': 'Action.OpenUrl', 'title': 'Open the dashboard', 'url': url, 'style': 'positive'}]
    return json.dumps(card, ensure_ascii=False)
def _block(colour, tag_key, tag, title, items):
    url = dashboard_url()
    if _have((f'bar-{colour}', f'tag-{tag_key}')):
        top = [{'type': 'Image', 'url': f'{url}assets/card-bar-{colour}.png', 'size': 'Stretch', 'altText': ''},
               {'type': 'Image', 'url': f'{url}assets/card-tag-{tag_key}.png', 'height': '22px', 'altText': tag, 'spacing': 'Medium'}]
        sep = False
    else:
        top = [_tb(tag.upper(), size='Small', weight='Bolder', color='Warning' if colour == 'amber' else 'Accent')]; sep = True
    return {'type': 'Container', 'spacing': 'Large', 'separator': sep, 'items': top + ([_tb(title, size='Large', weight='Bolder', spacing='Small')] if title else []) + items}
def _sub(title): return _tb(title, weight='Bolder', spacing='Large', separator=True)

HEADSUP_TODO = 'As a precaution, be ready to pause ramp work. Stay alert and work carefully.'

def headsup_message(d, airports, new_ty, test=False):
    """One message for every new heads-up found at this refresh."""
    parts = []; text = []; blocks = []; subj = []
    if airports:
        rows_ = [[f'<strong>{esc(a["name"])}</strong>' + (' <span style="color:' + MUTED + ';font-size:11.5px">(estimate)</span>' if a.get('est') else ''), esc(a.get('what')), esc(a.get('when'))] for a in airports]
        title = 'Thunderstorm expected at ' + (airports[0]['name'] if len(airports) == 1 else f'{len(airports)} airports')
        parts.append(_section(AMBER, 'Heads-up', title, _table(['Airport', 'What is expected', 'When'], rows_, ['34%', '38%', '28%']), f'<strong>What to do.</strong> {esc(HEADSUP_TODO)}'))
        text.append('HEADS-UP: ' + title + '\n' + '\n'.join(f"- {a['name']}: {a.get('what')}, {a.get('when')}" for a in airports) + f'\nWhat to do: {HEADSUP_TODO}\n')
        items = [_cols([_tb('Airport', size='Small', isSubtle=True), _tb('What is expected', size='Small', isSubtle=True), _tb('When', size='Small', isSubtle=True)], ['34', '38', '28'])]
        items += [_cols([_tb('**' + a['name'] + '**' + (' (estimate)' if a.get('est') else '')), a.get('what'), a.get('when')], ['34', '38', '28']) for a in airports]
        items.append({'type': 'Container', 'style': 'emphasis', 'spacing': 'Medium', 'items': [_tb('**What to do.** ' + HEADSUP_TODO)]})
        blocks.append(_block('amber', 'headsup', 'Heads-up', title, items))
        subj.append('Thunderstorm expected: ' + (', '.join(a['name'] for a in airports) if len(airports) <= 2 else f'{len(airports)} airports'))
    if new_ty:
        parts.append(_section(AMBER, 'Heads-up', str(d.get('ty_banner')), f'<div style="{FONT};font-size:13.5px;line-height:1.55;color:{INK}">{esc(d.get("ty_text"))}</div>'))
        text.append('HEADS-UP: ' + str(d.get('ty_banner')) + '\n' + str(d.get('ty_text')) + '\n')
        blocks.append(_block('amber', 'headsup', 'Heads-up', str(d.get('ty_banner')), [_tb(d.get('ty_text'))]))
        subj.append('Typhoon watch')
    n = len(airports) + (1 if new_ty else 0)
    intro = 'Advance notice from the Airport Weather Monitoring dashboard. This is a forecast, not something happening at the airport yet.'
    subject = ('TEST | ' if test else '') + 'Airport Weather heads-up: ' + ' | '.join(subj)
    if len(subject) > 90: subject = subject[:87] + '...'
    body = _shell(d, subject, 'Heads-up', intro, ''.join(parts))
    url = dashboard_url()
    teams = '<b>Heads-up.</b> ' + '<br>'.join(esc(t).replace('\n', '<br>') for t in text) + (f'<br><a href="{esc(url)}">Open the dashboard</a>' if url else '')
    return subject, intro + '\n\n' + '\n'.join(text) + (f'\nDashboard: {url}\n' if url else ''), body, teams, _card(d, 'Heads-up', intro, blocks, test)

def briefing_message(d, slot_hour, now_ms, test=False):
    """The whole picture: today, tomorrow, typhoon watch and recent earthquakes."""
    A = d.get('airports', []); order = {'danger': 0, 'warning': 1, 'advisory': 2}
    att = sorted([a for a in A if a.get('level') in order], key=lambda a: (order[a['level']], a['name']))
    cnt = {lv: sum(1 for a in A if a.get('level') == lv) for lv in ('danger', 'warning', 'advisory', 'normal')}
    tmr = sorted([a for a in A if a.get('t')], key=lambda a: (a.get('tsort', 9), a['name']))
    recent = [q for q in d.get('quakes', []) if q.get('ms') and now_ms - q['ms'] <= 24 * 3600000]
    name = 'Morning briefing' if slot_hour < 12 else 'Afternoon briefing'
    day_ = pht(now_ms); daytxt = f"{day_.strftime('%A')}, {day_.strftime('%b')} {day_.day}"
    summary = f"{cnt['danger']} Danger, {cnt['warning']} Warning, {cnt['advisory']} Advisory, {cnt['normal']} Normal"
    pill = lambda lv: f'<span style="display:inline-block;background:{LEVEL_HEX[lv]};color:#FFFFFF;{FONT};font-size:10.5px;font-weight:700;letter-spacing:.04em;padding:2px 7px;border-radius:4px;text-transform:uppercase">{LEVEL_NAME[lv]}</span>'
    est = lambda a: ' <span style="color:' + MUTED + ';font-size:11.5px">(estimate)</span>' if a.get('est') else ''
    parts = []; blocks = []; text = [f'{name.upper()}, {daytxt}', f'Today: {summary}.', '']
    # today
    if att:
        inner = _table(['Level', 'Airport', 'What', 'When'], [[pill(a['level']), f'<strong>{esc(a["name"])}</strong>{est(a)}', esc(a.get('what')), esc(a.get('when'))] for a in att], ['17%', '29%', '30%', '24%'])
        items = [_cols([_tb(LEVEL_NAME[a['level']], weight='Bolder', color={'danger': 'Attention', 'warning': 'Warning', 'advisory': 'Default'}[a['level']]), _tb('**' + a['name'] + '**'), a.get('what'), a.get('when')], ['18', '28', '30', '24']) for a in att[:CARD_ROWS_TODAY]]
        if len(att) > CARD_ROWS_TODAY: items.append(_tb(f'and {len(att) - CARD_ROWS_TODAY} more on the dashboard.', size='Small', isSubtle=True))
        text += ['TODAY'] + [f"- {LEVEL_NAME[a['level']]}: {a['name']}. {a.get('what')}, {a.get('when')}" for a in att] + ['']
    else:
        inner = f'<div style="{FONT};font-size:13.5px;color:{INK}">All 36 airports are Normal.</div>'; items = [_tb('All 36 airports are Normal.')]; text += ['TODAY', 'All airports are Normal.', '']
    parts.append(_section(NAVY, 'Daily briefing', f'Today: {summary}', inner))
    blocks.append(_block('navy', 'briefing', 'Daily briefing', f'Today: {summary}', items))
    # tomorrow
    if tmr:
        parts.append(_section(NAVY, '', 'Tomorrow (forecast, less certain)', _table(['Airport', 'What', 'When'], [[f'<strong>{esc(a["name"])}</strong>', esc(a.get('twhat')), esc(a.get('twhen'))] for a in tmr], ['34%', '38%', '28%'])))
        blocks.append({'type': 'Container', 'items': [_sub('Tomorrow (forecast, less certain)')] + [_cols(['**' + a['name'] + '**', a.get('twhat'), a.get('twhen')], ['34', '38', '28']) for a in tmr[:CARD_ROWS_TOMORROW]] +
                       ([_tb(f'and {len(tmr) - CARD_ROWS_TOMORROW} more on the dashboard.', size='Small', isSubtle=True)] if len(tmr) > CARD_ROWS_TOMORROW else [])})
        text += ['TOMORROW'] + [f"- {a['name']}: {a.get('twhat')}, {a.get('twhen')}" for a in tmr] + ['']
    # typhoon
    ty = str(d.get('ty_text') or d.get('ty_banner') or '')
    if ty:
        parts.append(_section(AMBER if typhoon_active(d) else NAVY, '', 'Typhoon watch', f'<div style="{FONT};font-size:13.5px;line-height:1.55;color:{INK}">{esc(ty)}</div>'))
        blocks.append({'type': 'Container', 'items': [_sub('Typhoon watch'), _tb(ty)]}); text += ['TYPHOON WATCH', ty, '']
    # earthquakes
    if recent:
        qrows = [[f'<strong>M{q["mag"]:.1f}</strong>', esc(q.get('place')), esc(clock(q['ms'])), esc(q.get('near'))] for q in recent]
        parts.append(_section(PURPLE, '', 'Earthquakes in the last 24 hours', _table(['Size', 'Where', 'When', 'Nearest airport'], qrows, ['11%', '37%', '22%', '30%']), esc(d.get('flag'))))
        blocks.append({'type': 'Container', 'items': [_sub('Earthquakes in the last 24 hours')] + [_cols([f"**M{q['mag']:.1f}**", q.get('place'), clock(q['ms']), q.get('near')], ['12', '38', '22', '28']) for q in recent] + [_tb(d.get('flag'), size='Small', isSubtle=True)]})
        text += ['EARTHQUAKES, LAST 24 HOURS'] + [f"- M{q['mag']:.1f}, {q.get('place')}, {clock(q['ms'])}. Nearest airport: {q.get('near')}" for q in recent] + ['']
    intro = f'{name} for {daytxt}: the weather picture across the 36 airports, with tomorrow\'s outlook.'
    subject = ('TEST | ' if test else '') + f"Airport Weather {name.lower()}, {day_.strftime('%b')} {day_.day}: {cnt['danger']} Danger, {cnt['warning']} Warning"
    body = _shell(d, subject, name, intro, ''.join(parts))
    url = dashboard_url()
    teams = '<br>'.join(esc(t) for t in text) + (f'<br><a href="{esc(url)}">Open the dashboard</a>' if url else '')
    return subject, '\n'.join(text) + (f'\nDashboard: {url}\n' if url else ''), body, teams, _card(d, name, intro, blocks, test)

def main():
    d = json.load(open(DATA, encoding='utf-8'))
    try: state = json.load(open(STATE, encoding='utf-8'))
    except Exception: state = {}
    first = not state
    now_ms = int(d.get('generated_ms') or dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    if os.environ.get('NOTIFY_CHECK'):
        # Only answers "is there anything to send at this refresh?" and records nothing. The workflow uses this to
        # publish the dashboard first, so that the alert and the dashboard agree when someone opens the link.
        q_, d_ = find_new(d, json.loads(json.dumps(state)), now_ms)
        pending = bool(q_ or d_)
        print('Alerts waiting to be sent:', len(q_) + len(d_))
        out = os.environ.get('GITHUB_OUTPUT')
        if out: open(out, 'a').write(f"pending={'true' if pending else 'false'}\n")
        return
    new_q, new_d = find_new(d, state, now_ms)
    if os.environ.get('NOTIFY_TEST', '').lower() in ('1', 'true', 'yes'):
        # Test button: sends a sample email built from whatever is on the dashboard now. Nothing is recorded as sent.
        tq = [(a, {q['id']: q for q in d.get('quakes', [])}.get(a.get('q'))) for a in d.get('eq_alerts', [])][:1]
        if not tq and d.get('quakes'): tq = [(dict(kind='strong', q=d['quakes'][0]['id'], text=''), d['quakes'][0])]
        td = [a for a in d.get('airports', []) if a.get('level') == 'danger'][:1] or [a for a in d.get('airports', []) if a.get('level') == 'warning'][:1]
        subject, plain, body = build_email(d, tq, td)
        subject = 'TEST | ' + subject
        note = 'THIS IS A TEST. It shows what an alert email looks like, using what is on the dashboard now. It is not a new alert.'
        body = body.replace('<div style="' + FONT + ';font-size:14px;line-height:1.55;color:' + INK + ';margin:0 0 16px">', '<div style="' + FONT + ';font-size:13.5px;font-weight:600;line-height:1.5;color:#7A4B00;background:#FFF4D6;border-radius:5px;padding:10px 12px;margin:0 0 14px">' + note + '</div><div style="' + FONT + ';font-size:14px;line-height:1.55;color:' + INK + ';margin:0 0 16px">', 1)
        try:
            if not deliver(subject, note + '\n\n' + plain, body, '<b>TEST, not a new alert.</b><br><br>' + teams_text(tq, td), teams_card(d, tq, td, test=True)): sys.exit('TEST FAILED: nothing is set up. Add the ALERT_WEBHOOK_URL secret (Power Automate), or SMTP_HOST and MAIL_TO (mail server).')
        except smtplib.SMTPAuthenticationError as e:
            sys.exit(f'TEST FAILED: the mail server refused the sign-in ({e.smtp_code}). Check SMTP_USER and SMTP_PASS; for Microsoft 365 the mailbox needs Authenticated SMTP switched on; for Gmail use an app password.')
        except Exception as e:
            sys.exit(f'TEST FAILED: {type(e).__name__}: {e}')
        try:
            wa = [a for a in d.get('airports', []) if a.get('level') == 'warning' and 'thunderstorm' in str(a.get('what', '')).lower()][:4] or [a for a in d.get('airports', []) if a.get('level') == 'warning'][:2]
            if wa and SEND_HEADSUP: deliver(*headsup_message(d, wa, False, test=True), tier='headsup')
            if SEND_BRIEFING: deliver(*briefing_message(d, pht(now_ms).hour, now_ms, test=True), tier='briefing')
        except Exception as e:
            sys.exit(f'TEST FAILED on the heads-up or briefing sample: {type(e).__name__}: {e}')
        print('TEST PASSED: the sample alert was accepted. Check the inbox and the junk folder (and the flow run history if you use Power Automate).')
        return
    preview = os.environ.get('NOTIFY_PREVIEW')
    if (new_q or new_d) and not (first and not preview and os.environ.get('NOTIFY_SKIP_FIRST') == '1'):
        subject, plain, body = build_email(d, new_q, new_d)
        if preview:
            open(preview, 'w', encoding='utf-8').write(body); print('Preview written:', subject)
        else:
            try: deliver(subject, plain, body, teams_text(new_q, new_d), teams_card(d, new_q, new_d))
            except smtplib.SMTPAuthenticationError as e:
                print(f'EMAIL NOT SENT: the mail server refused the sign-in ({e.smtp_code}). Check SMTP_USER and SMTP_PASS. It will be tried again at the next refresh.', file=sys.stderr)
                return
            except Exception as e:
                print('EMAIL ERROR:', type(e).__name__, e, file=sys.stderr)      # never stop the data refresh because of email
                return                                                           # state not saved, so it is tried again next run
    else:
        print('No new alerts to email.')
    # heads-up and daily briefing
    before = json.loads(json.dumps(state)); fresh = 'warn' not in state
    hu, new_ty = find_headsup(d, state, now_ms)
    hu = [a for a in hu if a['id'] not in {x['id'] for x in new_d}]
    slot = brief_slot(state, now_ms) if SEND_BRIEFING else None
    if first or fresh or not SEND_HEADSUP: hu, new_ty = [], False   # the first run with this feature only records what is already there
    try:
        if hu or new_ty:
            m = headsup_message(d, hu, new_ty)
            if preview: open(preview + '.headsup.html', 'w', encoding='utf-8').write(m[2]); print('Preview written:', m[0])
            else: deliver(*m, tier='headsup')
        if slot:
            m = briefing_message(d, int(slot.rsplit('-', 1)[1]), now_ms)
            if preview: open(preview + '.briefing.html', 'w', encoding='utf-8').write(m[2]); print('Preview written:', m[0])
            else: deliver(*m, tier='briefing')
            state['briefs'] = (state.get('briefs', []) + [slot])[-6:]
    except Exception as e:
        print('HEADS-UP OR BRIEFING ERROR:', type(e).__name__, e, file=sys.stderr)       # tried again at the next refresh
        before.setdefault('warn', {})
        json.dump(before, open(STATE, 'w', encoding='utf-8'), separators=(',', ':'))     # keeps the alerts already sent in this run
        return
    json.dump(state, open(STATE, 'w', encoding='utf-8'), separators=(',', ':'))

if __name__ == '__main__':
    main()
