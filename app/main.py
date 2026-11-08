"""Fortnite Chest Tracker - window: first-run setup wizard, then a small status window while tracking."""
import ctypes
import os
import queue
import sys
import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import messagebox

import tracker as T

BG, PANEL, FG, MUTED, GOLD, RED, GREEN = "#0d0f14", "#181b24", "#e8e8ee", "#8a8fa3", "#f5c542", "#ff6b6b", "#4cd97b"
FONT = "Segoe UI"

LANGS = (("en", "English"), ("fr", "Français"), ("es", "Español"))

S = {  # UI texts per language
    "welcome": {"en": "Welcome!", "fr": "Bienvenue !", "es": "¡Bienvenido!"},
    "intro": {"en": "This tool reads your Fortnite replays after each game and counts the chests you open "
                    "(and the ones you break). Everything stays on your PC.",
              "fr": "Ce tool lit tes replays Fortnite après chaque game et compte les coffres que tu ouvres "
                    "(et ceux que tu casses). Tout reste sur ton PC.",
              "es": "Esta herramienta lee tus repeticiones de Fortnite después de cada partida y cuenta los cofres que abres "
                    "(y los que rompes). Todo se queda en tu PC."},
    "name": {"en": "Your Fortnite name (exactly as in game)", "fr": "Ton pseudo Fortnite (exactement comme en jeu)",
             "es": "Tu nombre de Fortnite (exactamente como en el juego)"},
    "name_hint": {"en": "Used to find you in replays and shown on your dashboard.",
                  "fr": "Sert à te retrouver dans les replays et s'affiche sur ton tableau.",
                  "es": "Sirve para encontrarte en las repeticiones y aparece en tu panel."},
    "lang": {"en": "Language", "fr": "Langue", "es": "Idioma"},
    "next": {"en": "Next  →", "fr": "Suivant  →", "es": "Siguiente  →"},
    "back": {"en": "←  Back", "fr": "←  Retour", "es": "←  Atrás"},
    "need_name": {"en": "Enter your Fortnite name.", "fr": "Entre ton pseudo Fortnite.", "es": "Escribe tu nombre de Fortnite."},
    "step2": {"en": "Are replays turned on?", "fr": "Les replays sont-ils activés ?", "es": "¿Están activadas las repeticiones?"},
    "ok": {"en": "✔  Replays are turned on", "fr": "✔  Les replays sont activés", "es": "✔  Las repeticiones están activadas"},
    "ok_d": {"en": "Last replay: {d}. Your games will be counted.", "fr": "Dernier replay : {d}. Tes games seront comptées.",
             "es": "Última repetición: {d}. Tus partidas se contarán."},
    "off": {"en": "✖  Replays are turned off", "fr": "✖  Les replays sont désactivés", "es": "✖  Las repeticiones están desactivadas"},
    "off_d": {"en": "Without replays the tool can't count anything. Turn them on (see below), then play a game.",
              "fr": "Sans replays, le tool ne peut rien compter. Active-les (voir ci-dessous) puis lance une game.",
              "es": "Sin repeticiones la herramienta no puede contar nada. Actívalas (ver abajo) y juega una partida."},
    "unk": {"en": "?  Can't check yet", "fr": "?  Impossible de vérifier pour l'instant", "es": "?  Todavía no se puede comprobar"},
    "unk_d": {"en": "No replay found on this PC. Check the setting below and play a game: the tool will warn you if they are off.",
              "fr": "Aucun replay trouvé sur ce PC. Vérifie le réglage ci-dessous et lance une game : le tool te préviendra s'ils sont coupés.",
              "es": "No se encontró ninguna repetición en este PC. Revisa el ajuste de abajo y juega una partida: la herramienta te avisará si están desactivadas."},
    "how": {"en": "In Fortnite: Settings (gear) → Game tab → Replays section\n"
                  "→ \"Record Replays\": ON\n→ \"Record Large Team Replays\": ON (for squads)",
            "fr": "Dans Fortnite : Réglages (roue dentée) → onglet Jeu → section Replays\n"
                  "→ « Enregistrer les replays » : ACTIVÉ\n→ « Enregistrer les replays d'équipes nombreuses » : ACTIVÉ (pour les squads)",
            "es": "En Fortnite: Configuración (engranaje) → pestaña Juego → sección Repeticiones\n"
                  "→ \"Grabar repeticiones\": ACTIVADO\n→ \"Grabar repeticiones de equipos grandes\": ACTIVADO (para escuadrones)"},
    "recheck": {"en": "Check again", "fr": "Revérifier", "es": "Volver a comprobar"},
    "step3": {"en": "Last step", "fr": "Dernière étape", "es": "Último paso"},
    "startup": {"en": "Start the tool with Windows", "fr": "Lancer le tool au démarrage de Windows",
                "es": "Iniciar la herramienta con Windows"},
    "import": {"en": "Also count the replays already on my PC", "fr": "Compter aussi les replays déjà sur mon PC",
               "es": "Contar también las repeticiones que ya están en mi PC"},
    "import_d": {"en": "Fortnite only keeps your latest games (older ones are deleted).",
                 "fr": "Fortnite ne garde que tes dernières games (les plus anciennes sont effacées).",
                 "es": "Fortnite solo guarda tus últimas partidas (las más antiguas se borran)."},
    "finish": {"en": "Finish", "fr": "Terminer", "es": "Terminar"},
    "total": {"en": "chests opened in total", "fr": "coffres ouverts au total", "es": "cofres abiertos en total"},
    "last": {"en": "Last game: {c} chests · {top} · {k} kills", "fr": "Dernière game : {c} coffres · {top} · {k} kills",
             "es": "Última partida: {c} cofres · {top} · {k} eliminaciones"},
    "none": {"en": "No games yet: play one, it will show up here when it ends.",
             "fr": "Aucune game pour l'instant : joue, elle apparaîtra ici à la fin.",
             "es": "Todavía no hay partidas: juega una y aparecerá aquí al terminar."},
    "st_ok": {"en": "●  Tracking: each game is counted ~20 s after it ends",
              "fr": "●  Suivi actif : chaque game est comptée ~20 s après la fin",
              "es": "●  Seguimiento activo: cada partida se cuenta ~20 s después de terminar"},
    "st_off": {"en": "●  Replays are off in Fortnite: your games are not counted!",
               "fr": "●  Replays désactivés dans Fortnite : tes games ne sont pas comptées !",
               "es": "●  Las repeticiones están desactivadas en Fortnite: ¡tus partidas no se cuentan!"},
    "st_unk": {"en": "●  Tracking, waiting for your first game", "fr": "●  Suivi actif, en attente de ta première game",
               "es": "●  Seguimiento activo, esperando tu primera partida"},
    "open": {"en": "Open my dashboard", "fr": "Ouvrir mon tableau", "es": "Abrir mi panel"},
    "settings": {"en": "Settings", "fr": "Réglages", "es": "Ajustes"},
    "quit": {"en": "Quit", "fr": "Quitter", "es": "Salir"},
    "quit_q": {"en": "Tracking will stop and your next games won't be counted. Quit?",
               "fr": "Le suivi va s'arrêter et tes prochaines games ne seront plus comptées. Quitter ?",
               "es": "El seguimiento se detendrá y tus próximas partidas no se contarán. ¿Salir?"},
    "already": {"en": "Fortnite Chest Tracker is already running.", "fr": "Fortnite Chest Tracker est déjà ouvert.",
                "es": "Fortnite Chest Tracker ya está abierto."},
}


class App:
    def __init__(self, minimized=False):
        self.cfg = T.load_config()
        self.lang = (self.cfg or {}).get("lang") or "en"  # English by default
        self.root = tk.Tk()
        self.root.title(T.APP_NAME)
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.minsize(500, 0)  # same width on every step
        try:
            self.root.iconbitmap(default=resource("icon.ico"))
        except Exception:
            pass
        self.tracker = None
        self.events = queue.Queue()
        self.state = "unknown"
        if self.cfg:
            self.main_window()
            if minimized:
                self.root.iconify()
        else:
            self.wizard_names()

    def t(self, key, **kw):
        texts = S[key]
        return texts.get(self.lang, texts["en"]).format(**kw)

    # ---------------------------------------------------------- helpers
    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()
        frame = tk.Frame(self.root, bg=BG, padx=28, pady=24)
        frame.pack(fill="both", expand=True)
        return frame

    def label(self, parent, text, size=11, color=FG, bold=False, wrap=460, **pack):
        lbl = tk.Label(parent, text=text, bg=parent["bg"], fg=color, font=(FONT, size, "bold" if bold else "normal"),
                       wraplength=wrap, justify="left", anchor="w")
        lbl.pack(fill="x", **({"pady": (0, 6)} | pack))
        return lbl

    def button(self, parent, text, cmd, primary=True, side="right"):
        b = tk.Button(parent, text=text, command=cmd, font=(FONT, 10, "bold"), relief="flat", cursor="hand2",
                      bg=GOLD if primary else PANEL, fg=BG if primary else FG, activebackground="#ffd966",
                      padx=16, pady=7, bd=0)
        b.pack(side=side, padx=(8, 0))
        return b

    def footer(self, f):
        bar = tk.Frame(f, bg=BG)
        bar.pack(fill="x", pady=(18, 0))
        return bar

    # ---------------------------------------------------------- wizard
    def wizard_names(self):
        f = self.clear()
        self.root.geometry("")
        self.label(f, self.t("welcome"), 20, GOLD, True)
        self.label(f, self.t("intro"), 10, MUTED, pady=(0, 16))
        self.label(f, self.t("name"), 11, FG, True)
        self.name_var = tk.StringVar(value=(self.cfg or {}).get("player", ""))
        e = tk.Entry(f, textvariable=self.name_var, font=(FONT, 13), bg=PANEL, fg=FG, insertbackground=FG,
                     relief="flat", width=32)
        e.pack(fill="x", ipady=6)
        e.focus_set()
        self.label(f, self.t("name_hint"), 9, MUTED, pady=(4, 14))
        self.label(f, self.t("lang"), 11, FG, True)
        row = tk.Frame(f, bg=BG)
        row.pack(fill="x")
        self.lang_var = tk.StringVar(value=self.lang)
        for code, txt in LANGS:
            tk.Radiobutton(row, text=txt, value=code, variable=self.lang_var, command=self.change_lang,
                           bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=GOLD,
                           font=(FONT, 10)).pack(side="left", padx=(0, 16))
        bar = self.footer(f)
        self.button(bar, self.t("next"), self.after_names)
        self.root.bind("<Return>", lambda _e: self.after_names())

    def change_lang(self):
        self.lang = self.lang_var.get()
        name = self.name_var.get()
        self.wizard_names()
        self.name_var.set(name)

    def after_names(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning(T.APP_NAME, self.t("need_name"))
            return
        self.new_cfg = {"player": name, "lang": self.lang,
                        "startup": (self.cfg or {}).get("startup", False)}
        self.root.unbind("<Return>")
        self.wizard_replays()

    def wizard_replays(self):
        f = self.clear()
        self.label(f, self.t("step2"), 18, GOLD, True, pady=(0, 14))
        state, newest = T.replay_status()
        box = tk.Frame(f, bg=PANEL, padx=16, pady=14)
        box.pack(fill="x")
        color = {"ok": GREEN, "off": RED}.get(state, GOLD)
        title = {"ok": "ok", "off": "off"}.get(state, "unk")
        self.label(box, self.t(title), 13, color, True, wrap=430)
        d = datetime.fromtimestamp(newest).strftime("%d/%m/%Y %H:%M") if newest else ""
        self.label(box, self.t(title + "_d", d=d), 10, FG, wrap=430)
        self.label(f, self.t("how"), 10, MUTED, pady=(14, 0))
        bar = self.footer(f)
        self.button(bar, self.t("next"), self.wizard_options)
        self.button(bar, self.t("recheck"), self.wizard_replays, primary=False)
        self.button(bar, self.t("back"), self.wizard_names, primary=False, side="left")

    def wizard_options(self):
        f = self.clear()
        self.label(f, self.t("step3"), 18, GOLD, True, pady=(0, 14))
        self.startup_var = tk.BooleanVar(value=self.new_cfg.get("startup", False))
        self.import_var = tk.BooleanVar(value=True)
        for var, key in ((self.startup_var, "startup"), (self.import_var, "import")):
            tk.Checkbutton(f, text=self.t(key), variable=var, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG,
                           activeforeground=GOLD, font=(FONT, 11), anchor="w").pack(fill="x", pady=(4, 0))
        self.label(f, self.t("import_d"), 9, MUTED, pady=(2, 0))
        bar = self.footer(f)
        self.button(bar, self.t("finish"), self.finish)
        self.button(bar, self.t("back"), self.wizard_replays, primary=False, side="left")

    def finish(self):
        self.new_cfg["startup"] = bool(self.startup_var.get())
        first_run = self.cfg is None
        if first_run:
            # replays already on disk are ignored if the user unticked "import"
            self.new_cfg["skip_before"] = 0 if self.import_var.get() else datetime.now().timestamp()
        else:
            self.new_cfg["skip_before"] = self.cfg.get("skip_before", 0)
        self.cfg = self.new_cfg
        T.save_config(self.cfg)
        try:
            T.set_startup(self.cfg["startup"])
        except Exception as e:
            T.log(f"Startup setting failed: {e}")
        if self.tracker:  # settings changed while running: restart the watcher with the new config
            self.tracker.stop_event.set()
            self.tracker = None
        self.main_window()

    # ---------------------------------------------------------- main window
    def main_window(self):
        f = self.clear()
        top = tk.Frame(f, bg=BG)
        top.pack(fill="x")
        tk.Label(top, text=T.APP_NAME, bg=BG, fg=MUTED, font=(FONT, 10, "bold")).pack(side="left")
        tk.Label(top, text=self.cfg.get("player", ""), bg=BG, fg=FG, font=(FONT, 10)).pack(side="right")
        self.total_lbl = tk.Label(f, text="0", bg=BG, fg=GOLD, font=(FONT, 46, "bold"), anchor="w")
        self.total_lbl.pack(fill="x", pady=(10, 0))
        self.label(f, self.t("total"), 11, MUTED)
        self.last_lbl = self.label(f, "", 10, FG, pady=(10, 0))
        self.status_lbl = self.label(f, "", 10, GREEN, pady=(6, 0))
        bar = self.footer(f)
        self.button(bar, self.t("open"), self.open_dashboard)
        self.button(bar, self.t("settings"), self.settings, primary=False)
        self.button(bar, self.t("quit"), self.quit, primary=False, side="left")
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.refresh()
        if not self.tracker:
            # the watcher thread never touches Tk: it posts events, the window reads them every 500 ms
            self.tracker = T.Tracker(self.cfg, on_game=lambda *_: self.events.put(("game", None)),
                                     on_status=lambda s: self.events.put(("status", s)))
            self.tracker.start()
            if not getattr(self, "_polling", False):
                self._polling = True
                self.poll_events()

    def poll_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "game":
                    self.refresh()
                else:
                    self.set_status(value)
        except queue.Empty:
            pass
        self.root.after(500, self.poll_events)

    def refresh(self):
        if not hasattr(self, "total_lbl") or not self.total_lbl.winfo_exists():
            return
        con = T.db()
        r = T.rows(con)
        con.close()
        tot = T.totals(r)
        self.total_lbl.config(text=tot["chests"] if tot else "0")
        if r:
            x = r[0]
            top = f"Top {x['placement']}" if x["placement"] else "-"
            self.last_lbl.config(text=self.t("last", c=x["chests"] if x["chests"] is not None else "?", top=top,
                                             k=x["eliminations"] or 0))
        else:
            self.last_lbl.config(text=self.t("none"))
        self.set_status(self.state)

    def set_status(self, state):
        self.state = state
        if hasattr(self, "status_lbl") and self.status_lbl.winfo_exists():
            key, color = {"ok": ("st_ok", GREEN), "off": ("st_off", RED)}.get(state, ("st_unk", GREEN))
            self.status_lbl.config(text=self.t(key), fg=color)

    def open_dashboard(self):
        if not T.DASHBOARD.exists():
            con = T.db()
            T.write_dashboard(con, self.cfg)
            con.close()
        webbrowser.open(T.DASHBOARD.as_uri())

    def settings(self):
        self.lang = self.cfg.get("lang", self.lang)
        self.wizard_names()

    def quit(self):
        if messagebox.askyesno(T.APP_NAME, self.t("quit_q")):
            if self.tracker:
                self.tracker.stop_event.set()
            self.root.destroy()


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def single_instance():
    """Only one tracker at a time (otherwise games would be processed twice)."""
    ctypes.windll.kernel32.CreateMutexW(None, False, "FortniteChestTracker_single_instance")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # sharp text on high-DPI screens
    except Exception:
        pass
    if not single_instance():
        lang = (T.load_config() or {}).get("lang") or "en"
        messagebox.showinfo(T.APP_NAME, S["already"].get(lang, S["already"]["en"]))
        sys.exit(0)
    App(minimized="--minimized" in sys.argv).root.mainloop()
