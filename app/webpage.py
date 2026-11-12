"""Dashboard data: builds one JSON blob from the games table; site_template.html renders it (tabs, charts, drawer).

Labels are written in French here and translated in the page (EN / FR / ES), so there is one source of truth.
Treasure hunt data (weeks, prize ids, odds, Treasure Hours) comes from the public content.json of
LED-N/Fortnite-ChestCounter (MIT), cached in the data folder and refreshed once a day.
"""
import json
import math
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

CATALOG_URL = "https://raw.githubusercontent.com/LED-N/Fortnite-ChestCounter/main/content/content.json"
DAYS = ("Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim")
KIND_CODE = {"outfit": "outfit", "pickaxe": "pickaxe", "backbling": "backbling", "car": "car", "jam": "jam",
             "loading": "loading", "pirate-shop": "token", "token": "token"}
KIND_FR = {"outfit": "Tenue dorée", "pickaxe": "Pioche", "backbling": "Sac à dos", "car": "Décor de véhicule",
           "jam": "Piste de jam", "loading": "Écran de chargement", "token": "Accès Boutique Pirate"}
TYPE_FR = {"normal": "Normaux", "rare": "Rares", "relic": "Reliques", "buried": "Enterrés (esprit)", "booty": "Avis de recherche"}
TREASURE_ITEMS = {
    "WID_Relic_XP": "Esprit", "TreasureUnknown": "Trésor (gizmo ou récompense)",
    "GizmoPortableExtractor": "Extracteur portable", "GizmoPortableExtractorReload": "Extracteur portable (Reload)",
    "GizmoGoldenFirework": "Feu d'artifice doré", "GizmoExtractionAccelerator": "Accélérateur d'extraction",
    "GizmoLuckyLocator": "Localisateur chanceux", "GizmoSpriteLocator": "Localisateur d'esprit",
}
SPECIAL_CHESTS = {"RareChest": "Coffre rare", "RelicChest": "Coffre de relique", "BuriedChest": "Coffre à esprit (déterré)",
                  "BootyChest": "Coffre d'avis de recherche"}
CHEST_NORM = {"RelicChestV1": "RelicChest", "RelicChestV2": "RelicChest", "BootyChestV1": "BootyChest", "BootyChestV2": "BootyChest",
              "BuriedChestRelicFinder": "BuriedChest", "AlwaysSpawnChest": None, "FactionChest": None, "Chest": None, "ExtractionChest": None}
ITEM_ALIASES = {"WID_RelicExtractor_Consumable": "GizmoPortableExtractorReload", "WID_RelicExtractor": "GizmoPortableExtractor"}
OUT_OF_SIGHT = "Un mate (hors de vue)"
ALL_FEATURES = ["hunt", "squad", "stats", "goals", "calendar", "overlay"]


# ------------------------------------------------------------------ treasure-hunt catalog
def refresh_catalog(data_dir, log=lambda m: None):
    """Downloads the latest catalog (at most once every 20 h) and the reward pictures."""
    cat_path, img_dir = data_dir / "treasure_catalog.json", data_dir / "img"
    fresh = cat_path.exists() and datetime.now().timestamp() - cat_path.stat().st_mtime < 20 * 3600
    if not fresh:
        try:
            req = urllib.request.Request(CATALOG_URL, headers={"User-Agent": "fortnite-chest-tracker"})
            data = urllib.request.urlopen(req, timeout=15).read()
            json.loads(data)
            cat_path.write_bytes(data)
        except Exception as e:
            log(f"Treasure catalog not updated ({e})")
    try:
        img_dir.mkdir(parents=True, exist_ok=True)
        for p in _all_prizes(load_catalog(data_dir)):
            url = p.get("image") or ""
            dest = img_dir / (p["id"] + Path(url.split("?")[0]).suffix)
            if url.startswith("https://") and not dest.exists():
                req = urllib.request.Request(url, headers={"User-Agent": "fortnite-chest-tracker"})
                dest.write_bytes(urllib.request.urlopen(req, timeout=15).read())
    except Exception as e:
        log(f"Reward pictures not downloaded ({e})")


def load_catalog(data_dir):
    try:
        return json.loads((data_dir / "treasure_catalog.json").read_text(encoding="utf-8"))
    except Exception:
        return {"odds": [], "weeks": [], "treasureHours": []}


def _all_prizes(cat):
    out = [cat["pirateShop"]] if cat.get("pirateShop") else []
    for w in cat.get("weeks") or []:
        out += w.get("prizes") or []
    return out


def prize_map(cat):
    m = {}
    for p in _all_prizes(cat):
        for pid in p.get("prizeIds") or []:
            m[pid] = ("backbling" if "backbling" in p["id"] else KIND_CODE.get(p["kind"], p["kind"]), p["name"])
    return m


def _utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _local(dt):
    return dt.astimezone().replace(tzinfo=None)


def _dt(x):
    try:
        return datetime.fromisoformat(x["date"])
    except Exception:
        return None


def _th_windows(cat):
    return [(_local(_utc(h["start"])), _local(_utc(h["end"])), h.get("boosts") or {}, h.get("confirmed", True))
            for h in cat.get("treasureHours") or []]


def _boost(dt, kind, ths):
    for a, b, boosts, _ in ths:
        if dt and a <= dt < b:
            return float(boosts.get(kind, 1))
    return 1.0


# ------------------------------------------------------------------ treasure helpers
def mate_name(n):
    return "Mate anonyme" if not n or n.startswith("temp-") or n == "mate" else n


def treasure_key(item):
    if not item:
        return "TreasureUnknown"
    for pat, key in (("RelicExtractor", "GizmoPortableExtractor"), ("FlameCeleb", "GizmoGoldenFirework"), ("LuckyLocator", "GizmoLuckyLocator"),
                     ("RelicFinder", "GizmoSpriteLocator"), ("SmugglerExtractionKey", "GizmoExtractionAccelerator"),
                     ("ExtractionAccelerat", "GizmoExtractionAccelerator")):
        if pat in item:
            return key
    return item


def _tr(raw):
    """Treasure JSON of one game, item aliases applied, normal chests removed from the 'finds'."""
    try:
        t = json.loads(raw) if raw else {}
    except ValueError:
        return {}
    for i in t.get("items") or []:
        i["item"] = ITEM_ALIASES.get(i["item"], i["item"])
    ch = {}
    for k, n in (t.get("chests") or {}).items():
        k2 = CHEST_NORM.get(k, k)
        if k2:
            ch[k2] = ch.get(k2, 0) + n
    t["chests"] = ch
    t["mate_chests"] = [dict(c, kind=CHEST_NORM.get(c["kind"], c["kind"])) for c in t.get("mate_chests") or [] if CHEST_NORM.get(c["kind"], c["kind"])]
    return t


def _by_person(t):
    """{person: ({chest type: n}, {item: n})}; None = the player."""
    people = {None: ({}, {})}
    for k, n in (t.get("chests") or {}).items():
        people[None][0][k] = n
    for c in t.get("mate_chests") or []:
        ch = people.setdefault(mate_name(c.get("by")), ({}, {}))[0]
        ch[c["kind"]] = ch.get(c["kind"], 0) + 1
    for i in t.get("items") or []:
        if i["item"].startswith("Gizmo"):
            continue  # extractor picked up from the ground = event loot, not a treasure
        it = people.setdefault(None if i.get("me") else mate_name(i.get("by")), ({}, {}))[1]
        it[i["item"]] = it.get(i["item"], 0) + 1
    for tr in t.get("treasures") or []:
        who = None if tr.get("me") else (mate_name(tr["by"]) if tr.get("by") else OUT_OF_SIGHT)
        key = treasure_key(tr.get("item"))
        it = people.setdefault(who, ({}, {}))[1]
        it[key] = it.get(key, 0) + 1
    return people


def _label(key):
    if key in SPECIAL_CHESTS:
        return SPECIAL_CHESTS[key]
    return TREASURE_ITEMS.get(key, key.replace("WID_", "").replace("_", " "))


def _prize_label(pid, pm):
    kind, name = pm.get(pid) or (None, None)
    return f"{KIND_FR.get(kind, 'Récompense')} · {name}" if kind else "Récompense de coffre doré"


def _mode(p):
    if not p:
        return "Mode inconnu"
    q = p.lower()
    kind = ("Zéro construction" if "nobuild" in q else "Classé" if ("habanero" in q or "ranked" in q)
            else "Reload" if ("punchberry" in q or "reload" in q) else "Blitz" if "blitz" in q else "Battle Royale")
    for k, v in (("solo", "Solo"), ("duo", "Duo"), ("trio", "Trio"), ("squad", "Section")):
        if k in q:
            return f"{kind} · {v}"
    return kind


# ------------------------------------------------------------------ blocks
def _game(x, pm):
    t = _tr(x["treasure"])
    people = []
    for who, (ch, its) in _by_person(t).items():
        items = [[_label(k), n, "c"] for k, n in ch.items()] + [[_label(k), n, "g"] for k, n in its.items()]
        if items:
            people.append({"who": "Toi" if who is None else who, "me": who is None, "items": items})
    trs = t.get("treasures") or []
    return {
        "id": x["replay"] or x["date"], "d": x["date"], "m": _mode(x["mode"]), "est": False,
        "p": x["placement"], "n": x["total_players"], "c": x["chests"], "b": x["chests_broken"] or 0,
        "k": x["eliminations"] or 0, "a": x["assists"] or 0, "dm": x["weapon_damage"] or 0, "dt": x["damage_taken"] or 0,
        "ac": round(100 * (x["accuracy"] or 0)), "du": x["duration_s"] or 0, "pt": round((x["play_s"] or 0) * 0.9),
        "km": round((x["total_traveled_cm"] or 0) / 100000, 1), "ty": t.get("by_type") or {}, "pe": people,
        "pz": [{"l": _prize_label(p["id"], pm), "who": "Toi" if p.get("me") else mate_name(p.get("by"))} for p in t.get("prizes") or []],
        "tm": sum(1 for r in trs if r.get("me")), "tt": len(trs), "sq": [mate_name(m) for m in t.get("mates") or []],
    }


def _chances(rows, cat, now, pm, start):
    odds = {o["kind"]: o for o in cat.get("odds") or []}
    ths = _th_windows(cat)
    weeks = [(_local(_utc(w["start"])), _local(_utc(w["end"])), w) for w in cat.get("weeks") or []]
    wk = next(((a, b, w) for a, b, w in weeks if a <= now < b), None)
    games = [(_dt(x), x["chests"] or 0) for x in rows]
    got = {"gizmo": sum(1 for x in rows for r in (_tr(x["treasure"]).get("treasures") or []) if r.get("me"))}
    names = {"pirate-shop": "Accès Boutique Pirate", "gizmo": "Un gizmo (trésor)"}
    out = []
    for kind in ["pirate-shop", "outfit", "car", "pickaxe", "jam", "loading", "gizmo"]:
        o = odds.get(kind)
        if not o:
            continue
        n = o["oneIn"]
        pool = [(d, c) for d, c in games if (not o.get("weekly")) or (wk and d and wk[0] <= d < wk[1])]
        if kind == "pirate-shop" and start:
            pool = pool + [(None, start)]   # the token counts every chest, including the ones before the tool
        p = 1 - math.exp(sum(c * math.log1p(-min(0.999999, _boost(d, kind, ths) / n)) for d, c in pool))
        exp = sum(c * _boost(d, kind, ths) / n for d, c in pool)
        prizes = (wk[2].get("prizes") or []) if (wk and o.get("weekly")) else []
        item = next((z["name"] for z in prizes if z["kind"] == kind), None)
        bb = any(z["kind"] == kind and "backbling" in z["id"] for z in prizes)
        out.append({"tot": kind == "pirate-shop", "kc": "token" if kind == "pirate-shop" else kind,
                    "l": "Sac à dos" if bb else (names.get(kind) or KIND_FR.get(kind, kind)), "n": n, "w": bool(o.get("weekly")),
                    "item": item, "c": sum(c for _, c in pool), "p": p, "e": exp, "g": got.get(kind, 0)})
    return out, (wk[2]["number"] if wk else None)


def _collection(rows, cat, now, img_dir):
    mine = {}
    for x in rows:
        for p in _tr(x["treasure"]).get("prizes") or []:
            if p.get("me"):
                mine[p["id"]] = (x["date"] or "")[:10]
    tok = cat.get("pirateShop")
    weeks = []
    for w in cat.get("weeks") or []:
        a, b = _local(_utc(w["start"])), _local(_utc(w["end"]))
        items = []
        for p in (w.get("prizes") or []) + ([tok] if tok else []):
            img = next((f"img/{f.name}" for f in img_dir.glob(p["id"] + ".*")), p.get("image") or "")
            kind = KIND_CODE.get(p["kind"], p["kind"])
            items.append({"k": "token" if kind == "token" else p["id"], "kc": kind, "name": p["name"], "img": img,
                          "kind": "Sac à dos" if "backbling" in p["id"] else KIND_FR.get(kind, kind),
                          "got": next((mine[i] for i in p.get("prizeIds") or [] if i in mine), None)})
        weeks.append({"n": w["number"], "t": w["title"], "a": a.strftime("%d/%m"), "b": b.strftime("%d/%m"),
                      "s": "cur" if a <= now < b else "past" if now >= b else "next", "known": bool(w.get("prizes")), "items": items})
    return weeks


def _th(cat, now):
    ths = _th_windows(cat)
    cur = next(((a, b, bo) for a, b, bo, _ in ths if a <= now < b), None)
    nxt = next(((a, b, bo, c) for a, b, bo, c in sorted(ths) if a > now), None)
    names = {"outfit": "tenue dorée", "pirate-shop": "jeton", "car": "voiture"}
    if cur:
        a, b, bo = cur
        return {"live": True, "end": int(b.timestamp()), "b": [[names.get(k, k), v] for k, v in bo.items()], "a": a.strftime("%H:%M"), "z": b.strftime("%H:%M")}
    if nxt:
        a, b, bo, conf = nxt
        return {"live": False, "start": int(a.timestamp()), "b": [[names.get(k, k), v] for k, v in bo.items()],
                "dw": a.weekday(), "dd": a.strftime("%d/%m"), "a": a.strftime("%H:%M"), "z": b.strftime("%H:%M"), "conf": conf}
    return None


def _session(rows, now):
    g = sorted(((_dt(x), x) for x in rows if _dt(x)), key=lambda t: t[0], reverse=True)
    if not g:
        return None
    ses = [g[0]]
    for d, x in g[1:]:
        if ses[-1][0] - d <= timedelta(minutes=45) + timedelta(seconds=x["duration_s"] or 0):
            ses.append((d, x))
        else:
            break
    start, end = ses[-1][0], g[0][0] + timedelta(seconds=g[0][1]["duration_s"] or 0)
    h = max((end - start).total_seconds() / 3600, 0.01)
    c = sum(x["chests"] or 0 for _, x in ses)
    return {"live": now - g[0][0] <= timedelta(minutes=70), "a": start.strftime("%d/%m %H:%M"), "z": end.strftime("%H:%M"),
            "c": c, "g": len(ses), "cph": round(c / h), "t": sum(len(_tr(x["treasure"]).get("treasures") or []) for _, x in ses),
            "w": sum(1 for _, x in ses if x["placement"] == 1), "k": sum(x["eliminations"] or 0 for _, x in ses)}


def _heat(rows):
    cells = {}
    for x in rows:
        d = _dt(x)
        if d:
            c = cells.setdefault(f"{d.weekday()}-{d.hour}", [0, 0])
            c[0] += x["chests"] or 0
            c[1] += 1
    return cells


def build(rows, totals, records, cfg, data_dir, live_since, now, ver, saved):
    cat = load_catalog(data_dir)
    pm = prize_map(cat)
    start = int(cfg.get("start_chests") or 0)
    tracked = sum(x["chests"] or 0 for x in rows)
    broken = sum(x["chests_broken"] or 0 for x in rows)
    total = start + tracked
    broken += round(start * broken / tracked) if tracked else 0
    today = now.strftime("%Y-%m-%d")
    chances, wk = _chances(rows, cat, now, pm, start)
    types, team, seen = {}, {"me": {}, "mates": {}}, []
    for x in rows:
        t = _tr(x["treasure"])
        for k, v in (t.get("by_type") or {}).items():
            types[k] = types.get(k, 0) + v
        if t:
            for who, (ch, its) in _by_person(t).items():
                dst = team["me"] if who is None else team["mates"]
                for k, n in list(ch.items()) + list(its.items()):
                    dst[_label(k)] = dst.get(_label(k), 0) + n
        for p in t.get("seen_prizes") or []:
            seen.append({"d": x["date"], "who": p.get("who") or "?", "l": _prize_label(p["id"], pm)})
    play = sum((x["play_s"] or 0) * 0.9 for x in rows)
    gizmo_odds = next((o["oneIn"] for o in cat.get("odds") or [] if o["kind"] == "gizmo"), 127)
    since = cfg.get("installed_at") or (rows[-1]["date"] if rows else now.isoformat(sep=" "))
    return {
        "player": cfg.get("player") or "", "lang": cfg.get("lang") or "en", "features": cfg.get("features") or ALL_FEATURES,
        "ver": ver, "gen": int(now.timestamp()), "live": int(live_since) if live_since else 0,
        "total": total, "opened": total - broken, "broken": broken, "since": f"{since[8:10]}/{since[5:7]}",
        "today": sum(x["chests"] or 0 for x in rows if (x["date"] or "").startswith(today)),
        "k": {"games": totals["games"] if totals else 0, "wins": totals["wins"] if totals else 0, "top10": totals["top10"] if totals else 0,
              "kills": totals["kills"] if totals else 0, "kd": totals["kd"] if totals else 0, "cpg": totals["chests_pg"] if totals else 0,
              "dpg": totals["dmg_pg"] if totals else 0, "acc": totals["acc"] if totals else "-",
              "time": f"{play / 3600:.1f} h", "cph": round(tracked / (play / 3600)) if play else 0},
        "games": [_game(x, pm) for x in rows], "session": _session(rows, now), "th": _th(cat, now),
        "chances": chances, "week_n": wk,
        "luck": {"real": sum(1 for x in rows for r in (_tr(x["treasure"]).get("treasures") or []) if r.get("me")), "exp": round(tracked / gizmo_odds)},
        "collection": _collection(rows, cat, now, data_dir / "img"),
        "types": [[TYPE_FR[k], types.get(k, 0)] for k in TYPE_FR if types.get(k)],
        "team": team, "seen": sorted(seen, key=lambda s: s["d"] or "", reverse=True)[:30],
        "saved": saved, "heat": _heat(rows), "records": [[r[0][1], str(r[1]), r[2][1]] for r in records],
    }


def render(template_path, i18n_path, data):
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = Path(template_path).read_text(encoding="utf-8").replace("/*DATA*/", blob, 1)
    return page.replace("/*I18N*/", Path(i18n_path).read_text(encoding="utf-8"), 1)
