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
When this is set it is used, and the SMTP settings are ignored. The flow receives subject, html, text, teams.

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
        danger_now[aid] = now_ms
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
            subj.append(('Possible tsunami: ' if tsu else 'Earthquake ') + f"M{q['mag']:.1f}, {place}" + (f" ({pht(q['ms']).strftime('%I:%M %p').lstrip('0')})" if q.get('ms') else ''))
            text.append(f"{'POSSIBLE TSUNAMI' if tsu else 'EARTHQUAKE'}: {title}\nTime it happened: {when}\nWhere: {q.get('where')}\nMagnitude: {q.get('magnote') or q['mag']}\nNearest airport: {q.get('near')}\nTsunami: {q.get('tsu')}\nWhat to do: {action}\n")
        else:
            title = 'Possible tsunami' if tsu else 'Earthquake alert'; rows = [row('Details', a['text'])]; action = ''
            subj.append(title); text.append(a['text'] + '\n')
        cards.append(card(DARKRED if tsu else PURPLE, 'Possible tsunami' if tsu else 'Earthquake', title, rows, action))
    for a in new_d:
        rows = [row('Right now', a.get('now')), row('Rest of today', a.get('next')), row('Confidence', a.get('conf')), row('Updated', a.get('upd')), row('Source', a.get('src'))]
        cards.append(card(RED, 'Danger', a['name'], rows, a.get('todo')))
        text.append(f"DANGER: {a['name']}\nRight now: {a.get('now')}\nRest of today: {a.get('next')}\nWhat to do: {a.get('todo')}\nUpdated: {a.get('upd')}\n")
    if new_d: subj.append('Danger: thunderstorm at ' + ', '.join(a['name'] for a in new_d))
    subject = '[Airport Weather] ' + ' | '.join(subj)
    if len(subject) > 150: subject = subject[:147] + '...'
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
This is an automatic message. It is sent once for each new alert, when the dashboard collects its data (about every 20 minutes), so it can arrive some minutes after the event.
Earthquake figures are first reports and are often revised. This message supports, and does not replace, official PHIVOLCS and PAGASA bulletins and the station's own safety procedures.<br><br>
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

def send_webhook(subject, plain, body, teams):
    """Hand the email to a Power Automate flow, which sends it from Outlook (and can post to Teams)."""
    import urllib.request
    url = os.environ.get('ALERT_WEBHOOK_URL', '').strip()
    if not url: return False
    payload = json.dumps({'subject': subject, 'html': fragment(body), 'text': plain, 'teams': teams, 'dashboard': dashboard_url()}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f'Alert handed to the Power Automate flow (reply {r.status}): {subject}')
    return True

def deliver(subject, plain, body, teams=''):
    """Power Automate flow if ALERT_WEBHOOK_URL is set, otherwise the mail server."""
    if os.environ.get('ALERT_WEBHOOK_URL', '').strip(): return send_webhook(subject, plain, body, teams)
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

def main():
    d = json.load(open(DATA, encoding='utf-8'))
    try: state = json.load(open(STATE, encoding='utf-8'))
    except Exception: state = {}
    first = not state
    now_ms = int(d.get('generated_ms') or dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    new_q, new_d = find_new(d, state, now_ms)
    if os.environ.get('NOTIFY_TEST', '').lower() in ('1', 'true', 'yes'):
        # Test button: sends a sample email built from whatever is on the dashboard now. Nothing is recorded as sent.
        tq = [(a, {q['id']: q for q in d.get('quakes', [])}.get(a.get('q'))) for a in d.get('eq_alerts', [])][:1]
        if not tq and d.get('quakes'): tq = [(dict(kind='strong', q=d['quakes'][0]['id'], text=''), d['quakes'][0])]
        td = [a for a in d.get('airports', []) if a.get('level') == 'danger'][:1] or [a for a in d.get('airports', []) if a.get('level') == 'warning'][:1]
        subject, plain, body = build_email(d, tq, td)
        subject = '[TEST] ' + subject
        note = 'THIS IS A TEST. It shows what an alert email looks like, using what is on the dashboard now. It is not a new alert.'
        body = body.replace('<div style="' + FONT + ';font-size:14px;line-height:1.55;color:' + INK + ';margin:0 0 16px">', '<div style="' + FONT + ';font-size:13.5px;font-weight:600;line-height:1.5;color:#7A4B00;background:#FFF4D6;border-radius:5px;padding:10px 12px;margin:0 0 14px">' + note + '</div><div style="' + FONT + ';font-size:14px;line-height:1.55;color:' + INK + ';margin:0 0 16px">', 1)
        try:
            if not deliver(subject, note + '\n\n' + plain, body, '<b>TEST, not a new alert.</b><br><br>' + teams_text(tq, td)): sys.exit('TEST FAILED: nothing is set up. Add the ALERT_WEBHOOK_URL secret (Power Automate), or SMTP_HOST and MAIL_TO (mail server).')
        except smtplib.SMTPAuthenticationError as e:
            sys.exit(f'TEST FAILED: the mail server refused the sign-in ({e.smtp_code}). Check SMTP_USER and SMTP_PASS; for Microsoft 365 the mailbox needs Authenticated SMTP switched on; for Gmail use an app password.')
        except Exception as e:
            sys.exit(f'TEST FAILED: {type(e).__name__}: {e}')
        print('TEST PASSED: the sample alert was accepted. Check the inbox and the junk folder (and the flow run history if you use Power Automate).')
        return
    preview = os.environ.get('NOTIFY_PREVIEW')
    if (new_q or new_d) and not (first and not preview and os.environ.get('NOTIFY_SKIP_FIRST') == '1'):
        subject, plain, body = build_email(d, new_q, new_d)
        if preview:
            open(preview, 'w', encoding='utf-8').write(body); print('Preview written:', subject)
        else:
            try: deliver(subject, plain, body, teams_text(new_q, new_d))
            except smtplib.SMTPAuthenticationError as e:
                print(f'EMAIL NOT SENT: the mail server refused the sign-in ({e.smtp_code}). Check SMTP_USER and SMTP_PASS. It will be tried again at the next refresh.', file=sys.stderr)
                return
            except Exception as e:
                print('EMAIL ERROR:', type(e).__name__, e, file=sys.stderr)      # never stop the data refresh because of email
                return                                                           # state not saved, so it is tried again next run
    else:
        print('No new alerts to email.')
    json.dump(state, open(STATE, 'w', encoding='utf-8'), separators=(',', ':'))

if __name__ == '__main__':
    main()
