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
VERSION = "2.0.0"
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FortniteChestTracker"
CONFIG_PATH = DATA_DIR / "config.json"
DB_PATH = DATA_DIR / "games.db"
LOG_PATH = DATA_DIR / "log.txt"
DASHBOARD = DATA_DIR / "dashboard.html"
ARCHIVE = DATA_DIR / "replays"
COLLECTION = DATA_DIR / "collection.json"   # rewards ticked by hand in "Your collection"
SITE_STATE = DATA_DIR / "site_state.json"   # data version + game in progress (read by the page every 5 s)
SITE_PORT = 47321                           # local page: http://127.0.0.1:47321/ (this PC only)
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
# page files (bundled inside the exe by PyInstaller, next to this file in dev)
RES_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


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
    ("mode", "TEXT"), ("play_s", "INTEGER"), ("treasure", "TEXT"),   # v2: playlist, time really in game, treasure-hunt finds (JSON)
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
        s.update(replay=f.name, player=res.get("player"), added_at=datetime.now().isoformat(sep=" ", timespec="seconds"))
        apply_result(s, res)
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
        write_dashboard(con, cfg, live_game())
    return added


def apply_result(s, res):
    """Copies what ChestCounter found into the game row."""
    s["chests"] = res.get("chests_opened")
    s["chests_broken"] = res.get("chests_broken")
    if res.get("land_time") is not None and res.get("last_pos_time") is not None:
        s["play_s"] = max(0, round(res["last_pos_time"] - res["land_time"]))
    if res.get("team_won"):
        s["placement"] = 1  # the team won after the player died
    s["mode"] = res.get("playlist")
    if "treasure" in res:
        s["treasure"] = json.dumps({
            "items": res.get("treasure") or [], "chests": res.get("special_chests") or {}, "mate_chests": res.get("mate_chests") or [],
            "treasures": res.get("treasures") or [], "prizes": res.get("prizes") or [], "by_type": res.get("by_type") or {},
            "seen_prizes": res.get("seen_prizes") or [], "mates": res.get("mates") or []}, ensure_ascii=False)


def recount(con, cfg):
    """Reads every archived replay again with the current ChestCounter (after an update)."""
    n = 0
    for (name,) in con.execute("SELECT replay FROM games").fetchall():
        f = ARCHIVE / name
        res = count_chests(f, cfg) if f.exists() else None
        if not res or res.get("chests_opened") is None:
            continue
        s = {}
        apply_result(s, res)
        con.execute(f"UPDATE games SET {', '.join(k + ' = ?' for k in s)} WHERE replay = ?", [*s.values(), name])
        con.commit()
        n += 1
    return n


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


def totals(r, start=0):
    """start = chests opened before using the tool (entered at setup), added to the chest total only."""
    n = len(r)
    if not n:
        return None
    acc = [x["accuracy"] for x in r if x["accuracy"]]
    chests = sum(x["chests"] or 0 for x in r)
    kills = sum(x["eliminations"] or 0 for x in r)
    wins = sum(1 for x in r if x["placement"] == 1)
    return {
        "chests": fmt_int(chests + (start or 0)), "chests_pg": round(chests / n, 1), "games": n, "wins": wins,
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


def live_game():
    """Epoch start of a game in progress (a replay Fortnite is still writing), else None."""
    if not DEMOS.exists():
        return None
    now = time.time()
    for p in DEMOS.glob("*.replay"):
        try:
            st = p.stat()
        except OSError:
            continue
        if now - st.st_mtime < 120:  # still being written (Fortnite writes the replay in chunks)
            return st.st_ctime
    return None


def write_dashboard(con, cfg, live_since=None):
    import hashlib
    import webpage as S
    r = rows(con)
    start = int(cfg.get("start_chests") or 0)
    ver = hashlib.sha1(json.dumps([(x["replay"], x["chests"], x["treasure"]) for x in r] + [cfg.get("features"), cfg.get("lang"), start],
                                  default=str).encode()).hexdigest()[:12]
    try:
        saved = json.loads(COLLECTION.read_text(encoding="utf-8"))
    except Exception:
        saved = {}
    data = S.build(r, totals(r, start), records(r) if r else [], cfg, DATA_DIR, live_since, datetime.now(), ver, saved)
    data["port"] = SITE_PORT
    DASHBOARD.write_text(S.render(RES_DIR / "site_template.html", RES_DIR / "i18n.js", data), encoding="utf-8")
    SITE_STATE.write_text(json.dumps({"v": ver, "live": int(live_since) if live_since else 0}), encoding="utf-8")


# ---------------------------------------------------------------- local page server (127.0.0.1 only)
OVERLAY_HTML = """<!doctype html><meta charset=utf-8><title>Chest overlay</title>
<style>html,body{margin:0;background:transparent;font-family:Inter,"Segoe UI",system-ui,sans-serif;overflow:hidden}
.o{display:inline-flex;align-items:center;gap:14px;padding:12px 22px 12px 14px;border-radius:18px;background:rgba(11,12,16,.82);border:2px solid rgba(247,183,49,.6);color:#fff}
.o b{font-size:44px;font-weight:800;letter-spacing:-.04em;line-height:1}.o span{display:block;font-size:13px;color:#ffd56b;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
.o small{display:block;font-size:13px;color:#cfd3dd;margin-top:2px}.pop{animation:pop .6s}@keyframes pop{40%{transform:scale(1.12)}}</style>
<div class=o id=o><svg width=54 height=54 viewBox="0 0 32 32"><rect x=3 y=11 width=26 height=17 rx=4 fill="#f7b731"/><path d="M3 15a9 9 0 0 1 9-9h8a9 9 0 0 1 9 9v1H3z" fill="#ffd56b"/><rect x=13.5 y=14.5 width=5 height=7 rx=1.6 fill="#0b0c10"/></svg>
<div><span id=l></span><b id=n>0</b><small id=s></small></div></div>
<script>let last=null;const L={en:["Chests","last game"],fr:["Coffres","dernière game"],es:["Cofres","última partida"]};
function up(){fetch("/api/overlay",{cache:"no-store"}).then(r=>r.json()).then(d=>{const t=L[d.lang]||L.en;l.textContent=t[0];
 n.textContent=Number(d.total).toLocaleString({fr:"fr-FR",es:"es-ES"}[d.lang]||"en-US");s.textContent=d.last!=null?"+"+d.last+" · "+t[1]:"";
 if(last!==null&&d.total!==last){o.classList.remove("pop");void o.offsetWidth;o.classList.add("pop")}last=d.total}).catch(()=>{})}up();setInterval(up,5000)</script>"""


def start_server(cfg_ref):
    """Serves the dashboard on http://127.0.0.1:SITE_PORT/ (also saves the collection ticks and serves the OBS overlay)."""
    from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body if isinstance(body, bytes) else body.encode("utf-8"))

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/dashboard.html"):
                return self._send(200, DASHBOARD.read_bytes() if DASHBOARD.exists() else b"...")
            if path == "/api/state":
                return self._send(200, SITE_STATE.read_bytes() if SITE_STATE.exists() else b"{}", "application/json")
            if path == "/api/collection":
                return self._send(200, COLLECTION.read_bytes() if COLLECTION.exists() else b"{}", "application/json")
            if path == "/overlay":
                return self._send(200, OVERLAY_HTML)
            if path == "/api/overlay":
                con = db()
                r = rows(con)
                con.close()
                cfg = cfg_ref()
                tot = int(cfg.get("start_chests") or 0) + sum(x["chests"] or 0 for x in r)
                body = json.dumps({"total": tot, "last": r[0]["chests"] if r else None, "lang": cfg.get("lang", "en")})
                return self._send(200, body, "application/json")
            if path.startswith("/img/"):
                f = DATA_DIR / "img" / Path(path).name
                if f.is_file():
                    return self._send(200, f.read_bytes(), "image/webp" if f.suffix == ".webp" else "image/png")
            self._send(404, b"not found", "text/plain")

        def do_POST(self):
            if self.path != "/api/collection":
                return self._send(404, b"", "text/plain")
            n = int(self.headers.get("Content-Length") or 0)
            try:
                data = json.loads(self.rfile.read(min(n, 20000)) or b"{}")
                COLLECTION.write_text(json.dumps({str(k)[:80]: bool(v) for k, v in data.items()}, indent=1), encoding="utf-8")
                self._send(200, b'{"ok":true}', "application/json")
            except Exception as e:
                self._send(400, str(e), "text/plain")

    try:
        srv = ThreadingHTTPServer(("127.0.0.1", SITE_PORT), H)
    except OSError as e:
        log(f"Local page server not started ({e})")
        return False
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return True


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
        import webpage as S
        con = db()
        log(tr("watching", self.cfg.get("lang", "en"), path=DEMOS))
        S.refresh_catalog(DATA_DIR, log)
        if self.cfg.get("data_version", 1) < 2:   # first start of v2: read the old games again for the new stats
            recount(con, self.cfg)
            self.cfg["data_version"] = 2
            save_config(self.cfg)
        live = live_game()
        write_dashboard(con, self.cfg, live)
        last_page = time.time()
        while not self.stop_event.is_set():
            try:
                added = scan(con, self.cfg, self.on_game)
                self.check_replays()
                now_live = live_game()
                if added or bool(now_live) != bool(live) or time.time() - last_page > 600:   # live on / off, or every 10 min
                    if time.time() - last_page > 600:
                        S.refresh_catalog(DATA_DIR, log)
                    live = now_live
                    write_dashboard(con, self.cfg, live)
                    last_page = time.time()
            except Exception as e:
                log(f"Error: {e}")
            self.stop_event.wait(10 if live else CHECK_EVERY_S)
