"""Fortnite Chest Tracker - core: reads replays, stores one row per game in SQLite, writes the HTML dashboard.

Data lives in %LOCALAPPDATA%\\FortniteChestTracker (config.json, games.db, dashboard.html, log.txt, replays\\).
"""
import ctypes
import html
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from replay_reader import summarize

APP_NAME = "Fortnite Chest Tracker"
VERSION = "1.1.0"
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FortniteChestTracker"
CONFIG_PATH = DATA_DIR / "config.json"
DB_PATH = DATA_DIR / "games.db"
LOG_PATH = DATA_DIR / "log.txt"
DASHBOARD = DATA_DIR / "dashboard.html"
ARCHIVE = DATA_DIR / "replays"
FN_SAVED = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FortniteGame" / "Saved"
DEMOS = FN_SAVED / "Demos"
FN_LOG = FN_SAVED / "Logs" / "FortniteGame.log"
REPLAYS_OFF = "SupportsAutomaticClientReplayRecording returning false"
CHECK_EVERY_S = 20
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ChestCounter.exe sits next to the app exe (release) or in build\cc (dev)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent / "build" / "cc"
CHEST_EXE = BASE_DIR / "ChestCounter.exe"


# ---------------------------------------------------------------- language
def system_lang():
    try:
        return "fr" if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x0C else "en"
    except Exception:
        return "en"


TEXTS = {  # logs + notifications: key -> {lang: text}
    "game_added": {"en": "Game added ({date}): {chests} chests, {top}, {kills} kills",
                   "fr": "Partie ajoutée ({date}) : {chests} coffres, {top}, {kills} kills",
                   "es": "Partida añadida ({date}): {chests} cofres, {top}, {kills} eliminaciones"},
    "left": {"en": "left early", "fr": "partie quittée", "es": "abandonada"},
    "replays_off_log": {"en": "WARNING: replay recording is turned off in Fortnite, your games are not being counted!",
                        "fr": "ALERTE : l'enregistrement des replays est désactivé dans Fortnite, tes games ne sont pas comptées !",
                        "es": "AVISO: la grabación de repeticiones está desactivada en Fortnite, ¡tus partidas no se cuentan!"},
    "replays_off_title": {"en": "Replays are turned off!", "fr": "Replays désactivés !", "es": "¡Repeticiones desactivadas!"},
    "replays_off_text": {"en": "Your chests are not counted. Fortnite > Settings > Game > Replays: turn on Record Replays.",
                         "fr": "Tes coffres ne sont pas comptés. Fortnite > Réglages > Jeu > Replays : active Enregistrer les replays.",
                         "es": "Tus cofres no se cuentan. Fortnite > Configuración > Juego > Repeticiones: activa Grabar repeticiones."},
    "count_failed": {"en": "Could not count chests ({name}): {err}", "fr": "Comptage des coffres impossible ({name}) : {err}",
                     "es": "No se pudieron contar los cofres ({name}): {err}"},
    "unreadable": {"en": "Unreadable replay {name}: {err}", "fr": "Replay illisible {name} : {err}",
                   "es": "Repetición ilegible {name}: {err}"},
    "name_not_found": {"en": "Name \"{want}\" not found in {name}, tracking: {got}",
                       "fr": "Pseudo « {want} » introuvable dans {name}, joueur suivi : {got}",
                       "es": "Nombre \"{want}\" no encontrado en {name}, se sigue a: {got}"},
    "watching": {"en": "Watching replays: {path}", "fr": "Surveillance des replays : {path}", "es": "Vigilando repeticiones: {path}"},
}


def tr(key, lang, **kw):
    texts = TEXTS[key]
    return texts.get(lang, texts["en"]).format(**kw)


# ---------------------------------------------------------------- config
def load_config():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_config(cfg):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def set_startup(enabled):
    """Start with Windows (current user only) - only called when the user ticks the box."""
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled and getattr(sys, "frozen", False):
            winreg.SetValueEx(k, "FortniteChestTracker", 0, winreg.REG_SZ, f'"{sys.executable}" --minimized')
        else:
            try:
                winreg.DeleteValue(k, "FortniteChestTracker")
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------- replay setting check
def replay_status():
    """'ok' = replays are being recorded, 'off' = Fortnite says recording is disabled, 'unknown' = can't tell yet."""
    newest = max((p.stat().st_mtime for p in DEMOS.glob("*.replay")), default=0) if DEMOS.exists() else 0
    off_ts = None
    try:
        with open(FN_LOG, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if REPLAYS_OFF in line:
                    off_ts = line
        if off_ts:
            try:  # Fortnite log time is UTC: "[2026.11.07-12.42.42:729]"
                off_ts = datetime.strptime(off_ts[1:20], "%Y.%m.%d-%H.%M.%S").replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                off_ts = 0
    except FileNotFoundError:
        pass
    if off_ts is not None and off_ts >= newest:
        return "off", newest
    if newest:
        return "ok", newest
    return "unknown", 0


# ---------------------------------------------------------------- notifications / log
def notify(title, text):
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
        "$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
        "$t = $x.GetElementsByTagName('text'); $t.Item(0).InnerText = $env:FCT_T; $t.Item(1).InnerText = $env:FCT_B;"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Fortnite Chest Tracker').Show([Windows.UI.Notifications.ToastNotification]::new($x))"
    )
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps], creationflags=NO_WINDOW,
                         env={**os.environ, "FCT_T": title, "FCT_B": text})
    except Exception:
        pass


def log(msg):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return line


# ---------------------------------------------------------------- database
COLUMNS = [
    ("replay", "TEXT UNIQUE"), ("chests", "INTEGER"), ("chests_broken", "INTEGER"), ("player", "TEXT"),
    ("date", "TEXT"), ("duration_s", "INTEGER"), ("placement", "INTEGER"), ("total_players", "INTEGER"),
    ("eliminations", "INTEGER"), ("assists", "INTEGER"), ("accuracy", "REAL"), ("weapon_damage", "INTEGER"),
    ("other_damage", "INTEGER"), ("damage_taken", "INTEGER"), ("damage_to_structures", "INTEGER"),
    ("revives", "INTEGER"), ("materials_gathered", "INTEGER"), ("materials_used", "INTEGER"),
    ("total_traveled_cm", "INTEGER"), ("kill_feed", "INTEGER"), ("changelist", "INTEGER"), ("added_at", "TEXT"),
]


def db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    cols = ", ".join(f"{n} {t}" for n, t in COLUMNS)
    con.execute(f"CREATE TABLE IF NOT EXISTS games (id INTEGER PRIMARY KEY, {cols})")
    have = {r[1] for r in con.execute("PRAGMA table_info(games)")}
    for n, t in COLUMNS:
        if n not in have:
            con.execute(f"ALTER TABLE games ADD COLUMN {n} {t.replace(' UNIQUE', '')}")
    con.commit()
    return con


def rows(con):
    con.row_factory = sqlite3.Row
    r = con.execute("SELECT * FROM games ORDER BY date DESC").fetchall()
    con.row_factory = None
    return r


def count_chests(replay_path, cfg):
    """Runs ChestCounter.exe on one replay. Returns its JSON result (dict) or None."""
    lang = cfg.get("lang", "en")
    if not CHEST_EXE.exists():
        log(tr("count_failed", lang, name=Path(replay_path).name, err=f"{CHEST_EXE} missing"))
        return None
    try:
        args = [str(CHEST_EXE), str(replay_path)]
        if cfg.get("player"):
            args.insert(1, f"--player={cfg['player']}")
        out = subprocess.run(args, capture_output=True, text=True, timeout=300, creationflags=NO_WINDOW)
        res = json.loads(out.stdout)[0]
        if not res.get("ok"):
            log(tr("count_failed", lang, name=Path(replay_path).name, err=res.get("error")))
            return None
        want, got = (cfg.get("player") or "").strip(), res.get("player") or "?"
        if want and want.lower() != got.lower():
            log(tr("name_not_found", lang, want=want, name=Path(replay_path).name, got=got))
        return res
    except Exception as e:
        log(tr("count_failed", lang, name=Path(replay_path).name, err=e))
        return None


def scan(con, cfg, on_game=None):
    """Adds every finished game that is not in the database yet. Returns the number of games added."""
    if not DEMOS.exists():
        return 0
    lang = cfg.get("lang", "en")
    done = {r[0] for r in con.execute("SELECT replay FROM games")}
    added = 0
    for f in sorted(DEMOS.glob("*.replay"), key=lambda p: p.stat().st_mtime):
        mtime = f.stat().st_mtime
        if f.name in done or time.time() - mtime < 10 or mtime < cfg.get("skip_before", 0):
            continue
        try:
            s = summarize(f)
        except (PermissionError, EOFError):
            continue  # Fortnite is still writing it / game just started
        except Exception as e:
            log(tr("unreadable", lang, name=f.name, err=e))
            continue
        if s["is_live"]:
            continue  # game in progress
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        dest = ARCHIVE / f.name
        if not dest.exists():
            shutil.copy2(f, dest)  # Fortnite deletes old replays by itself
        res = count_chests(dest, cfg) or {}
        s.update(replay=f.name, chests=res.get("chests_opened"), chests_broken=res.get("chests_broken"),
                 player=res.get("player"), added_at=datetime.now().isoformat(sep=" ", timespec="seconds"))
        if res.get("team_won"):
            s["placement"] = 1  # the team won after the player died
        names = [n for n, _ in COLUMNS]
        con.execute(f"INSERT OR IGNORE INTO games ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})",
                    [s.get(n) for n in names])
        con.commit()
        added += 1
        top = f"Top {s['placement']}" if s.get("placement") else tr("left", lang)
        line = log(tr("game_added", lang, date=s["date"], chests=s["chests"], top=top, kills=s.get("eliminations") or 0))
        if on_game:
            on_game(s, line)
    if added:
        write_dashboard(con, cfg)
    return added


# ---------------------------------------------------------------- stats
LABELS = {  # dashboard cards: key -> (en, fr, es)
    "chests": ("Chests opened", "Coffres ouverts", "Cofres abiertos"),
    "chests_pg": ("Chests / game", "Coffres / partie", "Cofres / partida"),
    "games": ("Games", "Parties", "Partidas"), "wins": ("Wins", "Top 1", "Victorias"), "top10": ("Top 10", "Top 10", "Top 10"),
    "kills": ("Kills", "Kills", "Eliminaciones"), "kills_pg": ("Kills / game", "Kills / partie", "Elim. / partida"),
    "kd": ("K/D", "K/D", "K/D"), "dmg_pg": ("Damage / game", "Dégâts / partie", "Daño / partida"),
    "acc": ("Avg. accuracy", "Précision moy.", "Precisión media"), "time": ("Time played", "Temps de jeu", "Tiempo jugado"),
}


def fmt_int(n):
    return f"{n:,}".replace(",", " ")


def totals(r):
    n = len(r)
    if not n:
        return None
    acc = [x["accuracy"] for x in r if x["accuracy"]]
    chests = sum(x["chests"] or 0 for x in r)
    kills = sum(x["eliminations"] or 0 for x in r)
    wins = sum(1 for x in r if x["placement"] == 1)
    return {
        "chests": fmt_int(chests), "chests_pg": round(chests / n, 1), "games": n, "wins": wins,
        "top10": sum(1 for x in r if x["placement"] and x["placement"] <= 10), "kills": kills,
        "kills_pg": round(kills / n, 2), "kd": round(kills / ((n - wins) or 1), 2),
        "dmg_pg": round(sum(x["weapon_damage"] or 0 for x in r) / n),
        "acc": f"{100 * sum(acc) / len(acc):.1f} %" if acc else "-",
        "time": f"{sum(x['duration_s'] or 0 for x in r) / 3600:.1f} h",
        "_chests": chests,
    }


def fmt_day(date):
    return f"{date[8:10]}/{date[5:7]}/{date[:4]}" if date else "-"


def records(r):
    """Personal bests: list of ((label en, fr, es), value, (detail en, fr, es))."""
    out = []

    def best(col, labels, fmt=str, keep=lambda x: True):
        c = [x for x in r if x[col] is not None and keep(x)]
        if c:
            x = max(c, key=lambda x: x[col])
            d = fmt_day(x["date"]) + (f" · Top {x['placement']}" if x["placement"] else "")
            out.append((labels, fmt(x[col]), (d, d, d)))

    best("chests", ("Most chests in 1 game", "Plus de coffres en 1 game", "Más cofres en 1 partida"))
    best("eliminations", ("Most kills in 1 game", "Plus de kills en 1 game", "Más eliminaciones en 1 partida"))
    best("weapon_damage", ("Most damage in 1 game", "Plus de dégâts en 1 game", "Más daño en 1 partida"))
    best("assists", ("Most assists in 1 game", "Plus d'assists en 1 game", "Más asistencias en 1 partida"))
    best("accuracy", ("Best accuracy", "Meilleure précision", "Mejor precisión"), lambda v: f"{100 * v:.0f} %",
         keep=lambda x: (x["weapon_damage"] or 0) >= 300)  # otherwise 1 lucky shot = 100 %
    best("total_traveled_cm", ("Longest distance", "Plus longue distance", "Mayor distancia"), lambda v: f"{v / 100000:.1f} km")
    streak = best_s = 0
    end = None
    for x in sorted(r, key=lambda x: x["date"] or ""):
        streak = streak + 1 if x["placement"] == 1 else 0
        if streak > best_s:
            best_s, end = streak, x["date"]
    if best_s:
        d = fmt_day(end)
        out.append((("Wins in a row", "Top 1 d'affilée", "Victorias seguidas"), best_s,
                    (f"until {d}", f"jusqu'au {d}", f"hasta el {d}")))
    days = {}
    for x in r:
        if x["date"]:
            d = days.setdefault(x["date"][:10], [0, 0, 0])
            d[0] += x["placement"] == 1
            d[1] += x["chests"] or 0
            d[2] += 1
    if days:
        for i, labels in ((0, ("Most wins in 1 day", "Plus de Top 1 en 1 jour", "Más victorias en 1 día")),
                          (1, ("Most chests in 1 day", "Plus de coffres en 1 jour", "Más cofres en 1 día")),
                          (2, ("Most games in 1 day", "Plus de games en 1 jour", "Más partidas en 1 día"))):
            day, v = max(days.items(), key=lambda kv: kv[1][i])
            out.append((labels, v[i], (fmt_day(day),) * 3))
    return out


def write_dashboard(con, cfg):
    r = rows(con)
    t = totals(r)
    lang = cfg.get("lang", "en")
    name = html.escape(cfg.get("player") or "")

    def L(en, fr, es):  # all languages in the page, CSS shows the chosen one
        return "".join(f"<span class={c}>{html.escape(str(t))}</span>" for c, t in (("en", en), ("fr", fr), ("es", es)))

    if not t:
        body = f"<p class=empty>{L('No games yet: play a game, it will show up here when it ends.', 'Aucune partie pour l’instant : joue une game, elle apparaîtra ici à la fin.', 'Todavía no hay partidas: juega una y aparecerá aquí al terminar.')}</p>"
    else:
        cards = "".join(f"<div class=c><b>{html.escape(str(t[k]))}</b><span class=k>{L(*LABELS[k])}</span></div>" for k in LABELS)
        recs = "".join(f"<div class=r><b>{html.escape(str(v))}</b><span class=l>{L(*labels)}</span><span class=d>{L(*details)}</span></div>"
                       for labels, v, details in records(r))
        trs = "".join(
            f"<tr class='{'win' if x['placement'] == 1 else ''}'><td>{html.escape(str(x['date']))}</td><td class=ch>{x['chests'] if x['chests'] is not None else '?'}</td>"
            f"<td>{x['placement'] or '-'}</td><td>{x['eliminations'] or 0}</td><td>{x['assists'] or 0}</td><td>{x['weapon_damage'] or 0}</td>"
            f"<td>{x['damage_taken'] or 0}</td><td>{100 * (x['accuracy'] or 0):.0f} %</td>"
            f"<td>{(x['duration_s'] or 0) // 60} min</td><td>{(x['total_traveled_cm'] or 0) / 100000:.1f} km</td></tr>" for x in r)
        heads = "".join(f"<th>{L(*h)}</th>" for h in (
            ("Date", "Date", "Fecha"), ("Chests", "Coffres", "Cofres"), ("Place", "Top", "Puesto"),
            ("Kills", "Kills", "Elim."), ("Assists", "Assists", "Asist."), ("Damage", "Dégâts", "Daño"),
            ("Damage taken", "Dégâts subis", "Daño recibido"), ("Accuracy", "Précision", "Precisión"),
            ("Duration", "Durée", "Duración"), ("Distance", "Distance", "Distancia")))
        body = (f"<div class=big><b>{t['chests']}</b><span>{L('chests opened in total', 'coffres ouverts au total', 'cofres abiertos en total')}</span></div>"
                f"<div class=g>{cards}</div><h2>{L('Personal bests', 'Records', 'Récords')}</h2><div class=g>{recs}</div>"
                f"<h2>{L('All games', 'Toutes les games', 'Todas las partidas')}</h2><div style='overflow-x:auto'><table><tr>{heads}</tr>{trs}</table></div>")
    DASHBOARD.write_text(f"""<!doctype html><html lang={lang}><meta charset=utf-8><title>Fortnite Chest Tracker</title>
<meta name=viewport content="width=device-width,initial-scale=1"><meta http-equiv=refresh content=60>
<style>
body{{background:#0d0f14;color:#e8e8ee;font:15px system-ui,sans-serif;margin:0;padding:24px}}
.en,.fr,.es{{display:none}} html[lang=en] .en,html[lang=fr] .fr,html[lang=es] .es{{display:inline}}
.top{{display:flex;justify-content:space-between;align-items:center;margin:0 0 16px;gap:12px;flex-wrap:wrap}}
h1{{font-size:22px;margin:0}} h2{{font-size:16px;color:#f5c542;margin:0 0 10px;font-weight:600}}
.lang button{{background:#181b24;color:#8a8fa3;border:1px solid #2a2f3e;border-radius:8px;padding:6px 12px;font:600 13px system-ui;cursor:pointer;margin-left:6px}}
html[lang=fr] #b-fr,html[lang=en] #b-en,html[lang=es] #b-es{{background:#f5c542;color:#0d0f14;border-color:#f5c542}}
.g{{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:24px}}
.c{{background:#181b24;border-radius:10px;padding:12px 16px;min-width:110px}} .c b{{display:block;font-size:22px}} .c span{{color:#8a8fa3;font-size:12px}}
.r{{background:linear-gradient(160deg,#211d10,#181b24 60%);border:1px solid #3a3218;border-radius:10px;padding:12px 16px;min-width:150px}}
.r b{{display:block;font-size:24px;color:#f5c542}} .r .l{{display:block!important;font-size:13px;margin:2px 0}} .r .d{{color:#6b7085;font-size:11px}}
table{{border-collapse:collapse;width:100%}} td,th{{padding:7px 10px;border-bottom:1px solid #222634;text-align:left;white-space:nowrap}}
th{{color:#8a8fa3;font-weight:500}} td.ch{{color:#f5c542;font-weight:700}} tr.win td{{color:#f5c542;font-weight:600}}
.big{{margin:0 0 18px}} .big b{{font-size:64px;color:#f5c542;display:block;line-height:1}} .big span{{color:#8a8fa3}}
.empty{{color:#8a8fa3;font-size:17px;margin-top:40px}} .foot{{color:#555;font-size:12px}} a{{color:#8a8fa3}}
</style>
<div class=top><h1>{L('Fortnite Stats', 'Stats Fortnite', 'Estadísticas Fortnite')}{' — ' + name if name else ''}</h1>
<div class=lang><button id=b-en onclick="setLang('en')">EN</button><button id=b-fr onclick="setLang('fr')">FR</button><button id=b-es onclick="setLang('es')">ES</button></div></div>
{body}
<p class=foot>{L('Updated on', 'Mis à jour le', 'Actualizado el')} {datetime.now():%d/%m/%Y %H:%M} · Fortnite Chest Tracker v{VERSION}</p>
<script>
function setLang(l){{document.documentElement.lang=l;try{{localStorage.setItem('lang',l)}}catch(e){{}}}}
try{{var l=localStorage.getItem('lang');if(l)document.documentElement.lang=l}}catch(e){{}}
</script>""", encoding="utf-8")


# ---------------------------------------------------------------- background watcher
class Tracker(threading.Thread):
    """Checks the replay folder every 20 s. Callbacks are called from this thread."""

    def __init__(self, cfg, on_game=None, on_status=None):
        super().__init__(daemon=True)
        self.cfg, self.on_game, self.on_status = cfg, on_game, on_status
        self.stop_event = threading.Event()
        self._alerted = None

    def check_replays(self):
        state, _ = replay_status()
        if self.on_status:
            self.on_status(state)
        if state == "off":
            try:
                key = FN_LOG.stat().st_ctime  # one alert per Fortnite launch
            except FileNotFoundError:
                key = None
            if key != self._alerted:
                self._alerted = key
                lang = self.cfg.get("lang", "en")
                log(tr("replays_off_log", lang))
                notify(tr("replays_off_title", lang), tr("replays_off_text", lang))

    def run(self):
        con = db()
        log(tr("watching", self.cfg.get("lang", "en"), path=DEMOS))
        write_dashboard(con, self.cfg)
        while not self.stop_event.is_set():
            try:
                scan(con, self.cfg, self.on_game)
                self.check_replays()
            except Exception as e:
                log(f"Error: {e}")
            self.stop_event.wait(CHECK_EVERY_S)
