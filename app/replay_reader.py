"""Lecteur de fichiers .replay Fortnite (format Unreal Engine "local file replay").

On ne lit pas tout le flux réseau (très lourd et change à chaque saison) :
on lit seulement l'en-tête et les "événements" du replay, qui contiennent
le résumé de fin de partie (top, kills, dégâts, précision...).
"""
import struct
import datetime as dt
from Crypto.Cipher import AES

FILE_MAGIC = 0x1CA2E27F
HISTORY_COMPRESSION = 2
HISTORY_RECORDED_TIMESTAMP = 3
HISTORY_ENCRYPTION = 6
HISTORY_CUSTOM_VERSIONS = 7

CHUNK_HEADER, CHUNK_DATA, CHUNK_CHECKPOINT, CHUNK_EVENT = 0, 1, 2, 3


class Reader:
    def __init__(self, data: bytes):
        self.d = data
        self.p = 0

    def left(self):
        return len(self.d) - self.p

    def bytes(self, n):
        if n < 0 or self.p + n > len(self.d):
            raise EOFError(f"lecture hors limites ({n} octets à {self.p})")
        b = self.d[self.p:self.p + n]
        self.p += n
        return b

    def u8(self):
        return self.bytes(1)[0]

    def u16(self):
        return struct.unpack("<H", self.bytes(2))[0]

    def u32(self):
        return struct.unpack("<I", self.bytes(4))[0]

    def i32(self):
        return struct.unpack("<i", self.bytes(4))[0]

    def i64(self):
        return struct.unpack("<q", self.bytes(8))[0]

    def f32(self):
        return struct.unpack("<f", self.bytes(4))[0]

    def fstring(self):
        n = self.i32()
        if n == 0:
            return ""
        if n < 0:  # UTF-16
            raw = self.bytes(-n * 2)
            return raw.decode("utf-16-le", "replace").rstrip("\x00")
        raw = self.bytes(n)
        return raw.decode("latin-1").rstrip("\x00")


def _ticks_to_datetime(ticks):
    # DateTime .NET : ticks de 100 ns depuis l'an 1 (les 2 bits hauts = "kind")
    ticks &= 0x3FFFFFFFFFFFFFFF
    try:
        return dt.datetime(1, 1, 1) + dt.timedelta(microseconds=ticks / 10)
    except OverflowError:
        return None


def _decrypt(key, data):
    if not key:
        return data
    data = data[: len(data) - len(data) % 16]
    out = AES.new(key, AES.MODE_ECB).decrypt(data)
    pad = out[-1] if out else 0
    if 0 < pad <= 16 and out.endswith(bytes([pad]) * pad):
        out = out[:-pad]
    return out


def read_replay(path):
    with open(path, "rb") as f:
        data = f.read()
    r = Reader(data)

    if r.u32() != FILE_MAGIC:
        raise ValueError("ce n'est pas un fichier replay Unreal")
    info = {"file_version": r.u32()}
    if info["file_version"] >= HISTORY_CUSTOM_VERSIONS:
        for _ in range(r.i32()):
            r.bytes(16)
            r.i32()
    info["length_ms"] = r.u32()
    info["network_version"] = r.u32()
    info["changelist"] = r.u32()
    info["friendly_name"] = r.fstring()
    info["is_live"] = r.u32() != 0
    if info["file_version"] >= HISTORY_RECORDED_TIMESTAMP:
        info["timestamp"] = _ticks_to_datetime(r.i64())
    if info["file_version"] >= HISTORY_COMPRESSION:
        info["is_compressed"] = r.u32() != 0
    key = b""
    if info["file_version"] >= HISTORY_ENCRYPTION:
        info["is_encrypted"] = r.u32() != 0
        key = r.bytes(r.i32())
    if not info.get("is_encrypted"):
        key = b""

    header = {}
    events = []
    while r.left() >= 8:
        ctype = r.u32()
        size = r.i32()
        start = r.p
        if size < 0 or start + size > len(data):
            break  # replay encore en cours d'écriture / tronqué
        if ctype == CHUNK_HEADER:
            try:
                header = _parse_header(Reader(data[start:start + size]))
            except Exception:
                pass
        elif ctype == CHUNK_EVENT:
            c = Reader(data[start:start + size])
            ev = {
                "id": c.fstring(),
                "group": c.fstring(),
                "metadata": c.fstring(),
                "start": c.u32(),
                "end": c.u32(),
            }
            n = c.i32()
            ev["data"] = _decrypt(key, c.bytes(n))
            events.append(ev)
        r.p = start + size

    info["header"] = header
    info["events"] = events
    return info


def _parse_header(h):
    out = {}
    if h.u32() != 0x2CF5A13D:
        return out
    ver = h.u32()
    out["network_version"] = ver
    if ver >= 19:  # HISTORY_USE_CUSTOM_VERSION
        for _ in range(h.i32()):
            h.bytes(16)
            h.i32()
    out["checksum"] = h.u32()
    if ver < 19:
        out["engine_net_version"] = h.u32()
        out["game_net_version"] = h.u32()
    if ver >= 12:  # HISTORY_HEADER_GUID
        h.bytes(16)
    if ver >= 11:  # HISTORY_SAVE_FULL_ENGINE_VERSION
        out["major"] = h.u16()
        out["minor"] = h.u16()
        out["patch"] = h.u16()
        out["engine_changelist"] = h.u32()
        out["branch"] = h.fstring()
    return out


# ---------------------------------------------------------------- événements

def parse_match_stats(b):
    r = Reader(b)
    r.u32()  # version
    s = {
        "accuracy": r.f32(),
        "assists": r.u32(),
        "eliminations": r.u32(),
        "weapon_damage": r.u32(),
        "other_damage": r.u32(),
        "revives": r.u32(),
        "damage_taken": r.u32(),
        "damage_to_structures": r.u32(),
        "materials_gathered": r.u32(),
        "materials_used": r.u32(),
        "total_traveled_cm": r.u32(),
    }
    return s


def parse_team_stats(b):
    r = Reader(b)
    r.u32()  # version
    return {"placement": r.u32(), "total_players": r.u32()}


def summarize(path):
    """Résumé d'une partie : dict prêt à être mis en base."""
    info = read_replay(path)
    out = {
        "file": str(path),
        "date": info.get("timestamp").isoformat(sep=" ", timespec="seconds") if info.get("timestamp") else None,
        "duration_s": round(info["length_ms"] / 1000),
        "is_live": info["is_live"],
        "changelist": info["changelist"],
        "kill_feed": sum(1 for e in info["events"] if e["group"] == "playerElim"),
    }
    for e in info["events"]:
        try:
            if e["metadata"] == "AthenaMatchStats":
                out.update(parse_match_stats(e["data"]))
            elif e["metadata"] == "AthenaMatchTeamStats":
                out.update(parse_team_stats(e["data"]))
        except Exception:
            pass
    return out


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        info = read_replay(p)
        print("==", p)
        print({k: v for k, v in info.items() if k != "events"})
        groups = {}
        for e in info["events"]:
            k = (e["group"], e["metadata"])
            groups[k] = groups.get(k, 0) + 1
        for k, v in groups.items():
            print("  ", k, v)
        for e in info["events"]:
            if e["metadata"] in ("AthenaMatchStats", "AthenaMatchTeamStats"):
                print("  ", e["metadata"], len(e["data"]), e["data"].hex())
        print(summarize(p))
