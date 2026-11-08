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
VERSION = "1.3.0"
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
        write_dashboard(con, cfg, live_game())
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
        if now - st.st_mtime < 45:  # still being written
            return st.st_ctime
    return None


def write_dashboard(con, cfg, live_since=None):
    from dashboard import render
    r = rows(con)
    start = int(cfg.get("start_chests") or 0)
    DASHBOARD.write_text(render(r, totals(r, start), records(r) if r else [], cfg, VERSION, live_since), encoding="utf-8")


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
        live = live_game()
        write_dashboard(con, self.cfg, live)
        while not self.stop_event.is_set():
            try:
                added = scan(con, self.cfg, self.on_game)
                self.check_replays()
                now_live = live_game()
                if added or bool(now_live) != bool(live):  # "game in progress" banner on / off
                    live = now_live
                    write_dashboard(con, self.cfg, live)
            except Exception as e:
                log(f"Error: {e}")
            self.stop_event.wait(10 if live else CHECK_EVERY_S)
