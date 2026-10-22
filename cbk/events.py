# Log do backup: events.jsonl (para o watcher e para máquinas) + progress.log (para gente).
import json, threading, time

_lock = threading.Lock()


def emit(cfg, type_, **data):
    ev = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "type": type_, **data}
    with _lock:
        with open(cfg["events"], "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        with open(cfg["log"], "a", encoding="utf-8") as f:
            f.write(f"{ev['t'][11:]} {human(ev)}\n")
    return ev


def human(ev):
    d = {k: v for k, v in ev.items() if k not in ("t", "type")}
    path = d.pop("dest", d.pop("path", ""))
    rest = " ".join(f"{k}={v}" for k, v in d.items() if k != "group")
    return f"{ev['type'].upper()} {path} {rest}".strip()


def read(cfg):
    try:
        with open(cfg["events"], encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
    except FileNotFoundError:
        return []
