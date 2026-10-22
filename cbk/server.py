# Servidor local: a página do curso (no navegador, já logada) manda para cá os anexos (PUT)
# e os links dos vídeos (POST /video); aqui eles viram arquivos dentro de `dest`.
import http.server, json, os, queue, threading, urllib.parse
from . import client, events, hls, paths

FIELDS = ("videos_ok", "videos_err", "files")


class State:
    def __init__(self):
        self.q = queue.Queue()
        self.counts = dict.fromkeys(FIELDS, 0)
        self.current = []
        self.lock = threading.Lock()

    def snapshot(self):
        with self.lock:
            return {**self.counts, "current": list(self.current), "queued": self.q.qsize()}


def safe(cfg, rel):
    """Caminho dentro de `dest` (com nomes válidos neste sistema), ou None se tentar sair dele."""
    parts = paths.to_local(cfg, rel)
    if not parts:
        return None
    base = cfg["dest"]
    dest = os.path.realpath(os.path.join(base, *parts))
    inside = os.path.normcase(dest).startswith(os.path.normcase(base) + os.sep)
    return dest if inside else None


def rel(cfg, path):
    return os.path.relpath(path, cfg["dest"]).replace(os.sep, "/")


def worker(cfg, st):
    while True:
        job = st.q.get()
        dest = job["dest"]
        with st.lock:
            st.current.append(rel(cfg, dest))
        err = None
        for _ in range(cfg["video_retries"]):
            try:
                info = hls.download(job["url"], dest, job.get("kind", "hls"),
                                    {**cfg["video_headers"], **job.get("headers", {})}, cfg["segment_threads"])
                err = None
                break
            except Exception as e:
                err = f"{type(e).__name__}: {e}"[-300:]
        with st.lock:
            st.current.remove(rel(cfg, dest))
            st.counts["videos_err" if err else "videos_ok"] += 1
        if err:
            events.emit(cfg, "video_err", dest=rel(cfg, dest), group=job.get("group"), error=err)
        else:
            events.emit(cfg, "video_ok", dest=rel(cfg, dest), group=job.get("group"), **info)
        st.q.task_done()


def handler(cfg, st):
    aliases = {}
    if cfg["aliases"]:
        with open(os.path.expanduser(cfg["aliases"]), encoding="utf-8") as f:
            aliases = json.load(f)

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def reply(self, code, body=b"", ctype="text/plain"):
            if isinstance(body, (dict, list)):
                body, ctype = json.dumps(body, ensure_ascii=False).encode(), "application/json"
            self.send_response(code)
            self.send_header("Access-Control-Allow-Origin", cfg["origin"])
            self.send_header("Access-Control-Allow-Methods", "PUT, GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            # Chrome pede isso para uma página https falar com 127.0.0.1 (Private Network Access)
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)

        def body(self):
            return self.rfile.read(int(self.headers.get("Content-Length", 0)))

        def do_OPTIONS(self):
            self.reply(204)

        def do_GET(self):
            p = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(p.query)
            if p.path == "/ls":
                d = safe(cfg, qs.get("p", [""])[0])
                self.reply(200, sorted(f for f in os.listdir(d) if not f.endswith(".part"))
                           if d and os.path.isdir(d) else [])
            elif p.path == "/exists":
                d = safe(cfg, qs.get("p", [""])[0])
                self.reply(200, {"exists": bool(d and os.path.exists(d))})
            elif p.path == "/status":
                self.reply(200, st.snapshot())
            elif p.path == "/aliases":
                self.reply(200, aliases)
            elif p.path == "/client.js":
                self.reply(200, client.build_js(cfg, None).encode(), "text/javascript; charset=utf-8")
            elif p.path == "/ping":
                self.reply(200, {"ok": True, "name": cfg["name"]})
            else:
                self.reply(404)

        def do_POST(self):
            j = json.loads(self.body() or b"{}")
            if self.path == "/video":
                d = safe(cfg, j.get("dest", ""))
                if not d or not j.get("url"):
                    return self.reply(403)
                st.q.put({**j, "dest": d})
                events.emit(cfg, "video_queued", dest=rel(cfg, d), group=j.get("group"), kind=j.get("kind", "hls"))
                self.reply(200, b"queued")
            elif self.path == "/event":
                t = str(j.pop("type", "note"))
                events.emit(cfg, t, **j)
                self.reply(200)
            else:
                self.reply(404)

        def do_PUT(self):
            d = safe(cfg, urllib.parse.unquote(urllib.parse.urlparse(self.path).path.lstrip("/")))
            if not d:
                return self.reply(403)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            data = self.body()
            with open(d + ".part", "wb") as f:
                f.write(data)
            os.replace(d + ".part", d)
            with st.lock:
                st.counts["files"] += 1
            events.emit(cfg, "file", path=rel(cfg, d), size=len(data), group=urllib.parse.unquote(self.headers.get("X-Group") or "") or None)
            self.reply(200, b"saved")

    return H


def serve(cfg):
    os.makedirs(cfg["dest"], exist_ok=True)
    st = State()
    for _ in range(cfg["video_workers"]):
        threading.Thread(target=worker, args=(cfg, st), daemon=True).start()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", cfg["port"]), handler(cfg, st))
    events.emit(cfg, "server_start", dest=cfg["dest"], port=cfg["port"])
    print(f"ouvindo em http://127.0.0.1:{cfg['port']} -> {cfg['dest']}\nlog: {cfg['log']}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
