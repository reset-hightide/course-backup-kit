# Monta o script da página: client/core.js + adapters/<adaptador>.js + opções do config.
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_js(cfg, run):
    adapter = cfg.get("adapter")
    path = os.path.join(ROOT, "adapters", f"{adapter}.js")
    if not adapter or not os.path.exists(path):
        raise ValueError(f"adaptador não encontrado: adapters/{adapter}.js")
    parts = [open(os.path.join(ROOT, "client", "core.js"), encoding="utf-8").read(),
             open(path, encoding="utf-8").read()]
    opts = {"server": f"http://127.0.0.1:{cfg['port']}", **cfg.get("client", {})}
    parts.append(f"CourseBackup.configure({json.dumps(opts, ensure_ascii=False)});")
    if run:
        parts.append(f"CourseBackup.run({json.dumps(adapter)}, {{dry: {str(run == 'dry').lower()}}});")
    return "\n".join(parts)
