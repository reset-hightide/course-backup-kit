# Carrega o config.json e completa os valores padrão.
import json, os, re, unicodedata
from . import paths

DEFAULTS = {
    "port": 8765,
    "video_workers": 2,          # vídeos baixando ao mesmo tempo
    "segment_threads": 12,       # segmentos HLS em paralelo por vídeo
    "video_retries": 3,
    "video_headers": {},         # ex.: {"Origin": "...", "Referer": "..."}
    "aliases": None,             # JSON {"título da aula em minúsculas": "pasta existente"}
    "stall_minutes": 45,         # sem vídeo concluído por esse tempo = problema
    "safe_names": "auto",        # auto: nomes válidos no Windows só no Windows; "windows": sempre; "none"
    "notify": [{"type": "stdout"}],
}


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "curso"


def load(path):
    with open(path, encoding="utf-8") as f:
        cfg = {**DEFAULTS, **json.load(f)}
    for key in ("name", "dest", "origin"):
        if not cfg.get(key):
            raise SystemExit(f"config: falta a chave '{key}'")
    cfg["dest"] = os.path.realpath(os.path.expanduser(cfg["dest"]))
    cfg.setdefault("state_dir", os.path.join(paths.user_dir("data"), slug(cfg["name"])))
    cfg["state_dir"] = os.path.expanduser(cfg["state_dir"])
    os.makedirs(cfg["state_dir"], exist_ok=True)
    cfg["events"] = os.path.join(cfg["state_dir"], "events.jsonl")
    cfg["log"] = os.path.join(cfg["state_dir"], "progress.log")
    if not cfg["video_headers"]:
        cfg["video_headers"] = {"Origin": cfg["origin"], "Referer": cfg["origin"] + "/"}
    cfg["video_headers"].setdefault("User-Agent", "Mozilla/5.0")
    return cfg
