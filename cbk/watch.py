# Acompanha o events.jsonl e avisa quando: um módulo termina todos os vídeos, algo dá errado
# (erro de vídeo/aula, servidor parado, nada concluído há X minutos) e quando tudo termina.
#   watch            roda até o fim, mandando os avisos pelos destinos do config ("notify")
#   watch --once     imprime o primeiro aviso novo como JSON e sai (para um agente como o Claude Code
#                    relançar em background e mandar o aviso ele mesmo, ex.: pelo WhatsApp Web)
import json, os, time, urllib.request
from . import events, notify


def current_run(evs):
    """Eventos desde o último run_start de verdade (não dry run)."""
    start = max((i for i, e in enumerate(evs) if e["type"] == "run_start" and not e.get("dry")), default=None)
    return (evs[start]["t"], evs[start:]) if start is not None else (None, [])


def scan(evs):
    run_id, evs = current_run(evs)
    order, queued, ok, err = [], {}, {}, {}
    for e in evs:
        g = e.get("group") or "(sem módulo)"
        if e["type"] == "video_queued":
            if g not in queued:
                order.append(g)
            queued.setdefault(g, set()).add(e["dest"])
        elif e["type"] == "video_ok":
            ok[e["dest"]] = e
            err.pop(e["dest"], None)
        elif e["type"] == "video_err":
            err[e["dest"]] = e
    ended = any(e["type"] == "run_end" for e in evs)
    done = {}
    for i, g in enumerate(order):
        later = i < len(order) - 1
        if (ended or later) and all(d in ok or d in err for d in queued[g]):
            done[g] = (len(queued[g]), sum(d in err for d in queued[g]))
    total = sum(len(s) for s in queued.values())
    return {"run": run_id, "done": done, "order": order, "total": total, "ok": len(ok), "err": err,
            "finished": len(ok) + len(err), "ended": ended, "evs": evs}


def fmt_dur(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h}h{m:02d}" if h else f"{m} min"


def fmt_size(b):
    return f"{b / 1e9:.1f} GB" if b >= 1e9 else f"{b / 1e6:.0f} MB"


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def report(cfg):
    """Escreve `_Relatório do backup.md` na pasta do curso e devolve o caminho."""
    s = scan(events.read(cfg))
    evs = s["evs"]
    vids = [e for e in evs if e["type"] == "video_ok"]
    files = [e for e in evs if e["type"] == "file"]
    lesson_errs = [e for e in evs if e["type"] == "lesson_error"]
    size = sum(e.get("size", 0) for e in vids + files)
    lines = [f"# Relatório do backup: {cfg['name']}", "",
             f"- Início: {s['run'] or '-'}", f"- Fim: {evs[-1]['t'] if evs else '-'}",
             f"- Vídeos: {len(vids)} OK, {len(s['err'])} com erro ({fmt_dur(sum(e.get('duration', 0) for e in vids))} de aula)",
             f"- Arquivos: {len(files)}", f"- Tamanho: {fmt_size(size)}", "",
             "| Módulo | Vídeos | Erros |", "|---|---|---|"]
    lines += [f"| {g} | {n} | {e} |" for g, (n, e) in s["done"].items()]
    if s["err"] or lesson_errs:
        lines += ["", "## Erros", ""]
        lines += [f"- `{d}`: {e.get('error', '')}" for d, e in s["err"].items()]
        lines += [f"- {e.get('lesson', '')}: {e.get('error', '')}" for e in lesson_errs]
    path = os.path.join(cfg["dest"], "_Relatório do backup.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def message(cfg, ev):
    name = cfg["name"]
    if ev["kind"] == "group":
        g, n, e = ev["group"], ev["videos"], ev["errors"]
        tail = f", {e} com erro" if e else ", sem erros"
        return f"✅ Backup {name}: {g} concluído ({plural(n, 'vídeo')}{tail}). Total: {ev['ok']}/{ev['total']}."
    if ev["kind"] == "all_done":
        return f"🎉 Backup {name} terminou: {ev['ok']}/{ev['total']} vídeos, {ev['errors']} com erro. Relatório: {ev['report']}"
    return f"⚠️ Backup {name}: {ev['problem']} ({ev['ok']}/{ev['total']} vídeos prontos)"


def server_alive(cfg):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{cfg['port']}/ping", timeout=10).read()
        return True
    except Exception:
        return False


def watch(cfg, once=False, init=False, interval=20):
    seen_path = os.path.join(cfg["state_dir"], "announced.json")
    seen = {}
    if os.path.exists(seen_path):
        with open(seen_path, encoding="utf-8") as f:
            seen = json.load(f)

    def save():
        with open(seen_path, "w", encoding="utf-8") as f:
            json.dump(seen, f, ensure_ascii=False, indent=1)

    s = scan(events.read(cfg))
    if init:
        seen[s["run"] or "-"] = sorted(s["done"])
        save()
        print(json.dumps(seen[s["run"] or "-"], ensure_ascii=False))
        return
    known_errs = set(s["err"]) if once else set()
    known_lesson_errs = sum(e["type"] == "lesson_error" for e in s["evs"]) if once else 0
    last_fin, last_t = s["finished"], time.time()

    while True:
        s = scan(events.read(cfg))
        base = {"ok": s["ok"], "total": s["total"], "errors": len(s["err"])}
        out = []
        announced = seen.setdefault(s["run"] or "-", [])
        for g in s["order"]:
            if g in s["done"] and g not in announced:
                announced.append(g)
                out.append({"kind": "group", "group": g, "videos": s["done"][g][0], **base, "errors": s["done"][g][1]})
        for d in set(s["err"]) - known_errs:
            known_errs.add(d)
            out.append({"kind": "problem", "problem": f"erro no vídeo {d}: {s['err'][d].get('error', '')[:200]}", **base})
        lesson_errs = [e for e in s["evs"] if e["type"] == "lesson_error"]
        for e in lesson_errs[known_lesson_errs:]:
            out.append({"kind": "problem", "problem": f"erro na aula {e.get('lesson', '')}: {e.get('error', '')[:200]}", **base})
        known_lesson_errs = len(lesson_errs)

        all_done = s["ended"] and s["finished"] >= s["total"]
        if all_done and "__all__" not in announced:
            announced.append("__all__")
            out.append({"kind": "all_done", "report": report(cfg), **base})
        if s["finished"] != last_fin:
            last_fin, last_t = s["finished"], time.time()
        elif not all_done and s["run"] and time.time() - last_t > cfg["stall_minutes"] * 60:
            out.append({"kind": "problem", "problem": f"nenhum vídeo concluído há {cfg['stall_minutes']} min (travado?)", **base})
            last_t = time.time()
        server_down = s["run"] and not all_done and not server_alive(cfg)
        if server_down:
            out.append({"kind": "problem", "problem": "servidor local parado", **base})
        save()

        for ev in out:
            ev["message"] = message(cfg, ev)
            if once:
                print(json.dumps(ev, ensure_ascii=False), flush=True)
            else:
                notify.send(cfg, ev["message"])
        if (once and out) or all_done or server_down:
            return
        time.sleep(interval)
