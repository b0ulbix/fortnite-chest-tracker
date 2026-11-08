"""Fortnite Chest Tracker - HTML stats page (dashboard.html).

Navy / gold "match HUD" style, EN / FR / ES, inline SVG charts, live "game in progress" banner.
100 % local: system fonts only (Bahnschrift ships with Windows), no external resource, no network.
"""
import html
from datetime import datetime

VERSION_FOOT = "Fortnite Chest Tracker"


def esc(x):
    return html.escape(str(x))


def L(en, fr, es):
    """All three languages in the page; CSS shows the selected one."""
    return f"<span class=en>{esc(en)}</span><span class=fr>{esc(fr)}</span><span class=es>{esc(es)}</span>"


def tip(en, fr, es):
    return f'data-tip-en="{esc(en)}" data-tip-fr="{esc(fr)}" data-tip-es="{esc(es)}"'


def num(n, dec=0):
    """1 908 / 1,67 / 9,6 style (narrow spaces, comma decimals in FR/ES look, readable everywhere)."""
    if n is None:
        return "–"
    s = f"{n:,.{dec}f}".replace(",", " ")
    return s.replace(".", ",") if dec else s


def mmss(sec):
    sec = int(sec or 0)
    return f"{sec // 60}:{sec % 60:02d}"


def short_date(d):
    """'2026-11-08 19:00:12' -> '08/11 · 19:00'"""
    return f"{d[8:10]}/{d[5:7]} · {d[11:16]}" if d and len(d) >= 16 else (d or "–")


def axis(v):
    v = max(v, 1)
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000):
        k = -(-v // step)
        if k <= 4:
            return int(k * step), step
    return int(v), int(v)


# ------------------------------------------------------------------ charts (inline SVG)
W, H, PL, PR, PT, PB = 620, 250, 40, 14, 22, 30


def _frame(top, step, xlabels):
    y = lambda v: PT + (H - PT - PB) * (1 - v / top)
    out = [f'<line x1={PL} x2={W - PR} y1={y(v):.1f} y2={y(v):.1f} class=gl />'
           f'<text x={PL - 10} y={y(v) + 4:.1f} class=ax text-anchor=end>{v}</text>' for v in range(0, top + 1, step)]
    out += [f'<text x={x:.1f} y={H - 8} class=ax text-anchor=middle>{esc(t)}</text>' for x, t in xlabels]
    return "".join(out), y


def _xlabels(dates, xs):
    """Label the first game of each day."""
    seen, out = set(), []
    for d, x in zip(dates, xs):
        day = d[8:10] + "/" + d[5:7] if d else ""
        if day and day not in seen:
            seen.add(day)
            out.append((x, day))
    return out[:8]


def chart_chests(games):
    """Stacked bars per game: opened (gold) + broken (blue)."""
    n = len(games)
    top, step = axis(max((g["chests"] or 0 for g in games), default=1))
    cw = (W - PL - PR) / max(n, 1)
    bw = min(34, cw * 0.62)
    xs = [PL + i * cw + cw / 2 for i in range(n)]
    grid, y = _frame(top, step, _xlabels([g["date"] for g in games], xs))
    out = [grid]
    best = max(range(n), key=lambda i: games[i]["chests"] or 0) if n else None
    for i, g in enumerate(games):
        c, b = g["chests"] or 0, g["chests_broken"] or 0
        o = max(c - b, 0)
        x0 = xs[i] - bw / 2
        if o:
            out.append(f'<rect x={x0:.1f} y={y(o):.1f} width={bw:.1f} height={y(0) - y(o):.1f} rx=3 class=c-open />')
        if b:
            out.append(f'<rect x={x0:.1f} y={y(c):.1f} width={bw:.1f} height={max(y(o) - y(c) - 2, 1):.1f} rx=3 class=c-brk />')
        if i == best and c:
            out.append(f'<text x={xs[i]:.1f} y={y(c) - 8:.1f} class=val text-anchor=middle>{c}</text>')
        d = short_date(g["date"])
        out.append(f'<rect x={xs[i] - cw / 2:.1f} y={PT} width={cw:.1f} height={H - PT - PB} class=hit '
                   f'{tip(f"{d} · {c} chests ({o} opened, {b} broken)", f"{d} · {c} coffres ({o} ouverts, {b} cassés)", f"{d} · {c} cofres ({o} abiertos, {b} rotos)")} />')
    return f'<svg viewBox="0 0 {W} {H}" class=chart>{"".join(out)}</svg>'


def chart_total(games, start):
    """Cumulative chests, game after game (measured games only, the starting value is shown in the hero)."""
    n = len(games)
    cum, s = [], 0
    for g in games:
        s += g["chests"] or 0
        cum.append(s)
    top, step = axis(max(cum, default=1))
    xs = [PL + (W - PL - PR) * (i / max(n - 1, 1)) for i in range(n)]
    grid, y = _frame(top, step, _xlabels([g["date"] for g in games], xs))
    if n < 2:
        return f'<svg viewBox="0 0 {W} {H}" class=chart>{grid}</svg>'
    pts = " L".join(f"{x:.1f},{y(v):.1f}" for x, v in zip(xs, cum))
    out = [grid, f'<path d="M{xs[0]:.1f},{y(0):.1f} L{pts} L{xs[-1]:.1f},{y(0):.1f} Z" class=area />',
           f'<path d="M{pts}" class=line />',
           f'<circle cx={xs[-1]:.1f} cy={y(cum[-1]):.1f} r=4.5 class=dot />',
           f'<text x={xs[-1] - 6:.1f} y={y(cum[-1]) - 12:.1f} class=val text-anchor=end>{num(cum[-1])}</text>']
    for i, (g, x, v) in enumerate(zip(games, xs, cum)):
        d = short_date(g["date"])
        out.append(f'<circle cx={x:.1f} cy={y(v):.1f} r=10 class=hit {tip(f"{d} · {v} chests so far", f"{d} · {v} coffres au total", f"{d} · {v} cofres en total")} />')
    return f'<svg viewBox="0 0 {W} {H}" class=chart>{"".join(out)}</svg>'


def chart_kills(games):
    n = len(games)
    top, step = axis(max((g["eliminations"] or 0 for g in games), default=1))
    cw = (W - PL - PR) / max(n, 1)
    bw = min(30, cw * 0.55)
    xs = [PL + i * cw + cw / 2 for i in range(n)]
    grid, y = _frame(top, step, _xlabels([g["date"] for g in games], xs))
    out = [grid]
    best = max(range(n), key=lambda i: games[i]["eliminations"] or 0) if n else None
    for i, g in enumerate(games):
        k = g["eliminations"] or 0
        if k:
            out.append(f'<rect x={xs[i] - bw / 2:.1f} y={y(k):.1f} width={bw:.1f} height={y(0) - y(k):.1f} rx=3 class=c-kill />')
        if i == best and k:
            out.append(f'<text x={xs[i]:.1f} y={y(k) - 8:.1f} class=val text-anchor=middle>{k}</text>')
        d = short_date(g["date"])
        out.append(f'<rect x={xs[i] - cw / 2:.1f} y={PT} width={cw:.1f} height={H - PT - PB} class=hit '
                   f'{tip(f"{d} · {k} kills", f"{d} · {k} kills", f"{d} · {k} eliminaciones")} />')
    return f'<svg viewBox="0 0 {W} {H}" class=chart>{"".join(out)}</svg>'


def chart_place(games):
    """Placement per game: #1 at the top, #100 at the bottom."""
    pl = [g for g in games if g["placement"]]
    n = len(games)
    xs = [PL + 20 + (W - PL - PR - 40) * (i / max(n - 1, 1)) for i in range(n)]
    y = lambda p: PT + (H - PT - PB) * ((min(p, 100) - 1) / 99)
    out = [f'<line x1={PL} x2={W - PR} y1={y(v):.1f} y2={y(v):.1f} class=gl /><text x={PL - 10} y={y(v) + 4:.1f} class=ax text-anchor=end>#{v}</text>'
           for v in (1, 50, 100)]
    out += [f'<text x={x:.1f} y={H - 8} class=ax text-anchor=middle>{esc(t)}</text>' for x, t in _xlabels([g["date"] for g in games], xs)]
    first_win = True
    for g, x in zip(games, xs):
        p = g["placement"]
        if not p:
            continue
        cls = "pdot win" if p == 1 else "pdot"
        out.append(f'<circle cx={x:.1f} cy={y(p):.1f} r={5 if p == 1 else 4} class="{cls}" />')
        if p == 1 and first_win:
            first_win = False
            out.append(f'<text x={x:.1f} y={y(p) + 20:.1f} class=val text-anchor=middle>Top 1</text>')
        d = short_date(g["date"])
        out.append(f'<circle cx={x:.1f} cy={y(p):.1f} r=11 class=hit {tip(f"{d} · Top {p}", f"{d} · Top {p}", f"{d} · Puesto {p}")} />')
    return f'<svg viewBox="0 0 {W} {H}" class=chart>{"".join(out)}</svg>', len(pl)


# ------------------------------------------------------------------ page
CSS = """
:root{--bg:#070b1f;--card:rgba(17,24,56,.72);--card-b:rgba(120,140,220,.16);--t1:#f2f4ff;--t2:#b4bbdb;--t3:#7d86ad;
 --gold:#f5b524;--gold2:#ffd36a;--open:#d4930c;--brk:#3a8eea;--kill:#9887ee;--rank:#1fbf7a;
 --c-gray:#8d95b3;--c-gold:#f5c542;--c-orange:#ff8a3d;--c-purple:#b05cff;--c-blue:#3a8eea;--c-green:#3ddc84}
*{box-sizing:border-box}
html{background:var(--bg)}
body{margin:0;min-height:100vh;color:var(--t1);font:15px/1.4 Bahnschrift,"Segoe UI",system-ui,sans-serif;font-variant-numeric:tabular-nums;
 background:radial-gradient(900px 600px at 0 0,rgba(40,60,160,.35),transparent 60%),radial-gradient(1000px 700px at 100% 100%,rgba(110,40,170,.35),transparent 60%),
 linear-gradient(160deg,#08103a 0%,#070b1f 55%,#140a2e 100%);background-attachment:fixed}
.en,.fr,.es{display:none} html[lang=en] .en,html[lang=fr] .fr,html[lang=es] .es{display:inline}
.wrap{max-width:1240px;margin:0 auto;padding:26px clamp(14px,3vw,28px) 40px}
header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;margin-bottom:20px}
.brand{display:flex;gap:14px;align-items:center}
.brand h1{margin:0;font-size:34px;font-weight:700;font-style:italic;letter-spacing:.5px;font-stretch:condensed;line-height:1}
.brand h1 b{background:linear-gradient(180deg,var(--gold2),var(--gold) 60%,#e08a0c);-webkit-background-clip:text;background-clip:text;color:transparent}
.brand p{margin:6px 0 0;color:var(--t2);font-size:14px}
.right{display:flex;flex-direction:column;align-items:flex-end;gap:10px}
.pills{display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end}
.pill{border:1px solid var(--card-b);background:rgba(16,24,60,.8);border-radius:999px;padding:7px 14px;font-weight:700;font-size:14px;letter-spacing:.4px;text-transform:uppercase}
.pill.live{border-color:var(--gold);color:var(--t1)} .pill.live i{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--gold);margin-right:8px;animation:pulse 1.4s infinite}
.pill.idle{color:var(--t3)} .pill.idle i{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--rank);margin-right:8px}
@keyframes pulse{50%{opacity:.35}}
.seg{display:inline-flex;border:1px solid var(--card-b);border-radius:999px;padding:3px;background:rgba(16,24,60,.8)}
.seg button{border:0;background:none;color:var(--t3);font:700 12px Bahnschrift,system-ui;padding:5px 10px;border-radius:999px;cursor:pointer}
html[lang=en] #b-en,html[lang=fr] #b-fr,html[lang=es] #b-es{background:var(--gold);color:#1a1205}
.upd{color:var(--t3);font-size:12px}
.card{background:var(--card);border:1px solid var(--card-b);border-radius:14px;backdrop-filter:blur(8px)}
.live-banner{display:flex;align-items:center;gap:16px;padding:16px 18px;margin-bottom:18px;border-color:rgba(245,181,36,.55);
 background:linear-gradient(90deg,rgba(245,181,36,.10),rgba(17,24,56,.7))}
.live-banner .ic{color:var(--gold);font-size:26px} .live-banner b{font-size:19px;letter-spacing:.4px} .live-banner small{color:var(--gold2);font-size:14px;margin-left:6px}
.live-banner p{margin:2px 0 0;color:var(--t2);font-size:14px}
.top{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:18px}
.box{padding:18px 18px 16px}
.lab{color:var(--t2);font-size:13px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase}
.hero-n{display:flex;align-items:center;gap:18px;margin:10px 0 8px}
.hero-n .n{font-size:84px;font-weight:700;font-stretch:condensed;letter-spacing:-1px;line-height:1}
.hero-n .u{color:var(--t2);font-size:22px;font-weight:700;letter-spacing:1px;align-self:flex-end;margin-bottom:12px}
.sub{color:var(--t2);font-size:14px}
.split{display:flex;gap:4px;height:8px;margin:14px 0 10px;max-width:440px}
.split i{border-radius:99px} .split .o{background:var(--open)} .split .b{background:var(--brk)}
.leg{display:flex;gap:14px;color:var(--t2);font-size:13px;align-items:center;flex-wrap:wrap}
.leg i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.last-n{display:flex;align-items:center;gap:12px;margin:8px 0 18px}
.last-n .n{font-size:58px;font-weight:700;line-height:1} .last-n .u{color:var(--t2);font-size:19px;font-weight:700;letter-spacing:.6px}
.badge{border:1px solid var(--card-b);background:rgba(58,142,234,.15);color:#a9c9ff;border-radius:999px;padding:3px 10px;font-size:12px;font-weight:700;letter-spacing:.6px}
.facts{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.facts b{display:block;font-size:22px} .facts span{color:var(--t3);font-size:12px;letter-spacing:1px;text-transform:uppercase}
.kpis{display:grid;grid-template-columns:repeat(7,1fr);gap:12px;margin-bottom:30px}
.kpi{padding:14px 12px 12px;border-top:3px solid var(--c)}
.kpi b{display:block;font-size:28px;font-weight:700} .kpi span{color:var(--t2);font-size:13px}
h2{font-size:22px;font-style:italic;font-weight:700;letter-spacing:.6px;text-transform:uppercase;margin:6px 0 14px}
.charts{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:30px}
.ch{padding:18px 18px 10px} .ch h3{margin:0;font-size:16px;letter-spacing:.8px;text-transform:uppercase}
.ch .sub{font-size:13px;margin:2px 0 6px} .ch .head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
.chart{width:100%;height:auto;display:block}
.chart .gl{stroke:rgba(140,160,230,.14)} .chart .ax{fill:var(--t3);font-size:11px;font-family:Bahnschrift,system-ui}
.chart .val{fill:var(--t1);font-size:12px;font-weight:700;font-family:Bahnschrift,system-ui}
.chart .c-open{fill:var(--open)} .chart .c-brk{fill:var(--brk)} .chart .c-kill{fill:var(--kill)}
.chart .area{fill:rgba(255,255,255,.07)} .chart .line{fill:none;stroke:var(--open);stroke-width:2.2;stroke-linejoin:round}
.chart .dot{fill:var(--open)} .chart .pdot{fill:var(--rank)} .chart .pdot.win{fill:var(--gold)}
.chart .hit{fill:transparent;cursor:pointer} .chart .hit:hover{fill:rgba(255,255,255,.05)}
.recs{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:30px}
.rec{padding:12px 14px;border-color:rgba(245,181,36,.28);background:linear-gradient(180deg,rgba(60,50,30,.35),rgba(17,24,56,.72) 60%)}
.rec b{display:block;font-size:28px;font-weight:700} .rec .k{font-size:13px;font-weight:600} .rec .d{color:var(--t3);font-size:12px;margin-top:2px}
.tbl{overflow:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th{color:var(--t2);font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;text-align:right;padding:12px 12px;border-bottom:1px solid var(--card-b);white-space:nowrap}
td{padding:11px 12px;text-align:right;border-bottom:1px solid rgba(120,140,220,.10);white-space:nowrap;font-weight:600}
th:first-child,td:first-child{text-align:left}
tbody tr:hover td{background:rgba(255,255,255,.03)}
td .star{color:var(--gold)} tr.win td{color:var(--gold2)}
.empty{padding:30px;color:var(--t2);text-align:center;font-size:16px}
.foot{color:var(--t3);font-size:13px;text-align:center;margin-top:26px}
#tip{position:fixed;pointer-events:none;z-index:9;background:#f2f4ff;color:#0b1030;font:700 12px Bahnschrift,system-ui;padding:6px 9px;border-radius:7px;
 opacity:0;transform:translate(-50%,-135%);white-space:nowrap;box-shadow:0 8px 20px rgba(0,0,0,.35)}
@media (max-width:1100px){.kpis{grid-template-columns:repeat(4,1fr)}.recs{grid-template-columns:repeat(3,1fr)}}
@media (max-width:820px){.top,.charts{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,1fr)}.recs{grid-template-columns:repeat(2,1fr)}.facts{grid-template-columns:repeat(2,1fr)}}
"""

JS = """
function save(k,v){try{localStorage.setItem(k,v)}catch(e){}}
function setLang(l){document.documentElement.lang=l;save('lang',l)}
try{var l=localStorage.getItem('lang');if(l)document.documentElement.lang=l}catch(e){}
function ago(){var u=document.getElementById('upd');if(!u)return;var s=Math.round(Date.now()/1000-GEN);var lg=document.documentElement.lang;
 var t={en:['Updated just now','Updated {} min ago'],fr:['Mis à jour à l’instant','Mis à jour il y a {} min'],es:['Actualizado ahora mismo','Actualizado hace {} min']}[lg]||[];
 u.textContent=s<60?t[0]:t[1].replace('{}',Math.floor(s/60))}
function clock(){var c=document.getElementById('lt');if(!c||!LIVE)return;var s=Math.max(0,Math.round(Date.now()/1000-LIVE));
 c.textContent=Math.floor(s/60)+':'+String(s%60).padStart(2,'0')}
document.addEventListener('DOMContentLoaded',function(){ago();clock();setInterval(function(){ago();clock()},1000);
 var tp=document.getElementById('tip');
 document.addEventListener('mousemove',function(e){var el=e.target.closest('[data-tip-en]');if(!el){tp.style.opacity=0;return}
  var lg=document.documentElement.lang;tp.textContent=el.getAttribute('data-tip-'+(lg==='fr'||lg==='es'?lg:'en'));
  tp.style.left=e.clientX+'px';tp.style.top=e.clientY+'px';tp.style.opacity=1})});
"""

CHEST_SVG = """<svg width="{s}" height="{s}" viewBox="0 0 64 64" aria-hidden="true">
<defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd36a"/><stop offset="1" stop-color="#e0890c"/></linearGradient></defs>
<path d="M10 26a14 14 0 0 1 14-14h16a14 14 0 0 1 14 14v4H10z" fill="url(#cg)" stroke="#5a3507" stroke-width="2.5"/>
<rect x="10" y="30" width="44" height="22" rx="3" fill="url(#cg)" stroke="#5a3507" stroke-width="2.5"/>
<rect x="10" y="29" width="44" height="4" fill="#5a3507"/><rect x="20" y="14" width="4" height="38" fill="#5a3507" opacity=".55"/><rect x="40" y="14" width="4" height="38" fill="#5a3507" opacity=".55"/>
<rect x="27" y="26" width="10" height="13" rx="2" fill="#3b2405"/><rect x="30" y="29" width="4" height="6" rx="1" fill="#ffe7a3"/></svg>"""


def render(rows, totals, records, cfg, version, live_since=None, now=None):
    """rows: games (newest first). totals: tracker.totals(). records: tracker.records(). live_since: epoch of a game in progress."""
    now = now or datetime.now()
    lang = cfg.get("lang", "en")
    name = (cfg.get("player") or "").strip()
    start = int(cfg.get("start_chests") or 0)
    chrono = sorted(rows, key=lambda x: x["date"] or "")
    tracked = sum(x["chests"] or 0 for x in rows)
    broken = sum(x["chests_broken"] or 0 for x in rows)
    opened = tracked - broken
    total = start + tracked
    since = cfg.get("installed_at") or (chrono[0]["date"] if chrono else None)
    since_txt = short_date(since) if since else "–"

    # header
    pills = f'<span class=pill>{esc(name.upper())}</span>' if name else ""
    pills += (f'<span class="pill live"><i></i>{L("Game in progress", "Partie en cours", "Partida en curso")}</span>' if live_since
              else f'<span class="pill idle"><i></i>{L("Tracking", "Suivi actif", "Seguimiento activo")}</span>')
    banner = ""
    if live_since:
        banner = (f'<div class="card live-banner"><span class=ic>((•))</span><div><b>{L("GAME IN PROGRESS", "PARTIE EN COURS", "PARTIDA EN CURSO")}</b>'
                  f'<small>· <span id=lt>0:00</span></small><p>{L("Your chests will be counted ~20 s after the game ends.", "Tes coffres seront comptés ~20 s après la fin de la game.", "Tus cofres se contarán ~20 s después del final de la partida.")}</p></div></div>')

    # hero
    w_o = 440 * opened / tracked if tracked else 220
    hero = (f'<div class="card box"><div class=lab>{L("Total chests", "Coffres au total", "Cofres en total")}</div>'
            f'<div class=hero-n>{CHEST_SVG.format(s=72)}<span class=n>{num(total)}</span><span class=u>{L("CHESTS", "COFFRES", "COFRES")}</span></div>'
            + (f'<div class=sub>{L(f"{num(start)} at start + {num(tracked)} since {since_txt}", f"{num(start)} au départ + {num(tracked)} depuis le {since_txt}", f"{num(start)} al inicio + {num(tracked)} desde el {since_txt}")}</div>' if start
               else f'<div class=sub>{L(f"Tracked since {since_txt}", f"Suivi depuis le {since_txt}", f"Seguimiento desde el {since_txt}")}</div>')
            + f'<div class=split><i class=o style="width:{w_o:.0f}px"></i><i class=b style="width:{440 - w_o:.0f}px"></i></div>'
            f'<div class=leg>{L("Tracked games:", "Games suivies :", "Partidas seguidas:")} <span><i style="background:var(--open)"></i>{num(opened)} {L("opened", "ouverts", "abiertos")}</span>'
            f'<span><i style="background:var(--brk)"></i>{num(broken)} {L("broken", "cassés", "rotos")}</span></div></div>')

    if rows:
        g = rows[0]
        gb = g["chests_broken"] or 0
        place = f'Top {g["placement"]}' if g["placement"] else "–"
        last = (f'<div class="card box"><div class=lab>{L("Last game", "Dernière game", "Última partida")} · {esc(short_date(g["date"]))}</div>'
                f'<div class=last-n><span class=n>{g["chests"] if g["chests"] is not None else "?"}</span><span class=u>{L("CHESTS", "COFFRES", "COFRES")}</span>'
                + (f'<span class=badge>{L(f"INCL. {gb} BROKEN", f"DONT {gb} CASSÉS", f"INCL. {gb} ROTOS")}</span>' if gb else "")
                + f'</div><div class=facts><div><b>{place}</b><span>{L("of", "sur", "de")} {g["total_players"] or "–"}</span></div>'
                f'<div><b>{g["eliminations"] or 0}</b><span>{L("Kills", "Kills", "Elim.")}</span></div>'
                f'<div><b>{num(g["weapon_damage"] or 0)}</b><span>{L("Damage", "Dégâts", "Daño")}</span></div>'
                f'<div><b>{mmss(g["duration_s"])}</b><span>{L("Duration", "Durée", "Duración")}</span></div></div></div>')
    else:
        last = f'<div class="card box"><div class=lab>{L("Last game", "Dernière game", "Última partida")}</div><div class=empty>{L("Play a game: it shows up here when it ends.", "Joue une game : elle apparaît ici à la fin.", "Juega una partida: aparecerá aquí al terminar.")}</div></div>'

    body = ""
    if rows:
        t = totals
        kpis = [(t["games"], ("Games", "Games", "Partidas"), "--c-gray"), (t["wins"], ("Wins", "Top 1", "Victorias"), "--c-gold"),
                (t["top10"], ("Top 10", "Top 10", "Top 10"), "--c-orange"), (t["kills"], ("Kills", "Kills", "Eliminaciones"), "--c-purple"),
                (num(t["kd"], 2), ("K/D", "K/D", "K/D"), "--c-purple"), (num(t["chests_pg"], 1), ("Chests / game", "Coffres / game", "Cofres / partida"), "--c-gold"),
                (num(t["dmg_pg"]), ("Damage / game", "Dégâts / game", "Daño / partida"), "--c-blue"),
                (t["acc"].replace(".", ","), ("Avg. accuracy", "Précision moy.", "Precisión media"), "--c-green"),
                (t["time"].replace(".", ","), ("Time played", "Temps de jeu", "Tiempo jugado"), "--c-gray")]
        kpi_html = "".join(f'<div class="card kpi" style="--c:var({c})"><b>{esc(v)}</b><span>{L(*k)}</span></div>' for v, k, c in kpis)
        place_svg, n_placed = chart_place(chrono)
        charts = (
            f'<div class="card ch"><div class=head><div><h3>{L("Chests per game", "Coffres par game", "Cofres por partida")}</h3>'
            f'<div class=sub>{L("All your games · details in the table", "Toutes tes games · détail dans le tableau", "Todas tus partidas · detalle en la tabla")}</div></div>'
            f'<div class=leg><span><i style="background:var(--open)"></i>{L("opened", "ouverts", "abiertos")}</span><span><i style="background:var(--brk)"></i>{L("broken", "cassés", "rotos")}</span></div></div>'
            f'{chart_chests(chrono)}</div>'
            f'<div class="card ch"><h3>{L("Total chests", "Total de coffres", "Total de cofres")}</h3>'
            f'<div class=sub>{L("Progress, game after game", "Progression, game après game", "Progreso, partida tras partida")}</div>{chart_total(chrono, start)}</div>'
            f'<div class="card ch"><h3>{L("Kills per game", "Kills par game", "Eliminaciones por partida")}</h3>'
            f'<div class=sub>{L("All your games · details in the table", "Toutes tes games · détail dans le tableau", "Todas tus partidas · detalle en la tabla")}</div>{chart_kills(chrono)}</div>'
            f'<div class="card ch"><h3>{L("Placement per game", "Classement par game", "Puesto por partida")}</h3>'
            f'<div class=sub>{L(f"Top 1 at the top · {n_placed} ranked games", f"Top 1 tout en haut · {n_placed} games classées", f"Top 1 arriba · {n_placed} partidas clasificadas")}</div>{place_svg}</div>')
        recs = "".join(f'<div class="card rec"><b>{esc(v)}</b><div class=k>{L(*labels)}</div><div class=d>{L(*details)}</div></div>'
                       for labels, v, details in records)
        trs = "".join(
            f'<tr class={"win" if x["placement"] == 1 else ""}><td>{esc(short_date(x["date"]))}</td><td>{x["chests"] if x["chests"] is not None else "?"}</td>'
            f'<td>{max((x["chests"] or 0) - (x["chests_broken"] or 0), 0)}</td><td>{x["chests_broken"] or 0}</td>'
            f'<td>{"<span class=star>★</span> 1" if x["placement"] == 1 else (x["placement"] or "–")}</td><td>{x["eliminations"] or 0}</td>'
            f'<td>{x["assists"] or 0}</td><td>{num(x["weapon_damage"] or 0)}</td><td>{num(x["damage_taken"] or 0)}</td>'
            f'<td>{100 * (x["accuracy"] or 0):.0f} %</td><td>{mmss(x["duration_s"])}</td><td>{num((x["total_traveled_cm"] or 0) / 100000, 1)} km</td></tr>'
            for x in rows)
        heads = "".join(f"<th>{L(*h)}</th>" for h in (
            ("Date", "Date", "Fecha"), ("Chests", "Coffres", "Cofres"), ("Opened", "Ouverts", "Abiertos"), ("Broken", "Cassés", "Rotos"),
            ("Place", "Top", "Puesto"), ("Kills", "Kills", "Elim."), ("Assists", "Assists", "Asist."), ("Damage", "Dégâts", "Daño"),
            ("Damage taken", "Dégâts subis", "Daño recibido"), ("Accuracy", "Précision", "Precisión"), ("Duration", "Durée", "Duración"),
            ("Distance", "Distance", "Distancia")))
        body = (f'<div class=kpis>{kpi_html}</div><h2>{L("Charts", "Graphiques", "Gráficos")}</h2><div class=charts>{charts}</div>'
                f'<h2>{L("Personal bests", "Records perso", "Récords personales")}</h2><div class=recs>{recs}</div>'
                f'<h2>{L("All your games", "Toutes tes games", "Todas tus partidas")}</h2>'
                f'<div class="card tbl"><table><thead><tr>{heads}</tr></thead><tbody>{trs}</tbody></table></div>')

    return f"""<!doctype html><html lang={lang}><meta charset=utf-8><title>Chest Tracker{' — ' + esc(name) if name else ''}</title>
<meta name=viewport content="width=device-width,initial-scale=1"><meta http-equiv=refresh content={15 if live_since else 60}>
<style>{CSS}</style>
<div class=wrap>
<header>
 <div class=brand>{CHEST_SVG.format(s=54)}<div><h1>CHEST <b>TRACKER</b></h1>
  <p>{L("Your Fortnite stats, live", "Tes stats Fortnite, en direct", "Tus estadísticas de Fortnite, en directo")}</p></div></div>
 <div class=right><div class=pills>{pills}
  <div class=seg><button id=b-en onclick="setLang('en')">EN</button><button id=b-fr onclick="setLang('fr')">FR</button><button id=b-es onclick="setLang('es')">ES</button></div></div>
  <span class=upd id=upd></span></div>
</header>
{banner}
<div class=top>{hero}{last}</div>
{body}
<p class=foot>{L("100% local: nothing leaves your PC · Not affiliated with Epic Games. Fortnite is a trademark of Epic Games, Inc.",
               "100 % local : rien ne sort de ton PC · Non affilié à Epic Games. Fortnite est une marque d'Epic Games, Inc.",
               "100 % local: nada sale de tu PC · No afiliado a Epic Games. Fortnite es una marca de Epic Games, Inc.")} · v{esc(version)}</p>
</div>
<div id=tip></div>
<script>var GEN={int(now.timestamp())},LIVE={int(live_since) if live_since else 0};{JS}</script>"""
