#!/usr/bin/env python3
"""Curso falso para testar o kit sem depender de site nenhum (usado por e2e.py e pelo adapters/demo.js).

  python3 tests/fake_site.py [porta]     serve em http://127.0.0.1:8899 (padrão)

Gera com ffmpeg 3 vídeos HLS fMP4 curtos (variante de vídeo + faixa de áudio separada, como no
Cloudflare Stream), alguns anexos e uma API JSON:
  GET /api/modules            -> [{title, lessons: [{id, title}]}]
  GET /api/lessons/<id>       -> {title, video, duration, files: [{name, url}], html}
"""
import http.server, json, os, subprocess, sys, tempfile

COURSE = [
    {"title": "Módulo 1: Introdução", "lessons": [
        {"id": "a1", "title": "Boas-vindas", "video": True, "files": ["Slides.pdf", "Planilha.xlsx"]},
        {"id": "a2", "title": "Leia antes de começar", "video": False, "files": [], "html": "<p>Texto da aula.</p>"}]},
    {"title": "Módulo 2: Prática", "lessons": [
        {"id": "b1", "title": "Exercício 1/2", "video": True, "files": ["Exercício.xlsx"]},
        {"id": "b2", "title": "Exercício 2", "video": True, "files": []}]},
]


def make_hls(root, vid):
    d = os.path.join(root, "media", vid)
    os.makedirs(d, exist_ok=True)
    common = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    subprocess.run(common + ["-f", "lavfi", "-i", "testsrc=size=640x360:rate=25", "-t", "4", "-c:v", "libx264",
                             "-g", "25", "-f", "hls", "-hls_time", "1", "-hls_segment_type", "fmp4",
                             "-hls_fmp4_init_filename", "vinit.mp4", "-hls_segment_filename", f"{d}/v%03d.m4s",
                             f"{d}/video.m3u8"], check=True)
    subprocess.run(common + ["-f", "lavfi", "-i", "sine=frequency=440", "-t", "4", "-c:a", "aac",
                             "-f", "hls", "-hls_time", "1", "-hls_segment_type", "fmp4",
                             "-hls_fmp4_init_filename", "ainit.mp4", "-hls_segment_filename", f"{d}/a%03d.m4s",
                             f"{d}/audio.m3u8"], check=True)
    with open(f"{d}/master.m3u8", "w") as f:
        f.write('#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",NAME="pt",DEFAULT=YES,URI="audio.m3u8"\n'
                '#EXT-X-STREAM-INF:BANDWIDTH=100000,RESOLUTION=320x180,AUDIO="aud"\nvideo.m3u8\n'
                '#EXT-X-STREAM-INF:BANDWIDTH=900000,RESOLUTION=640x360,AUDIO="aud"\nvideo.m3u8\n')


def build(root):
    for m in COURSE:
        for l in m["lessons"]:
            if l["video"]:
                make_hls(root, l["id"])
            for fn in l["files"]:
                os.makedirs(os.path.join(root, "files", l["id"]), exist_ok=True)
                with open(os.path.join(root, "files", l["id"], fn), "wb") as f:
                    f.write(f"conteúdo de {fn}\n".encode() * 100)


def serve(root, port):
    base = f"http://127.0.0.1:{port}"
    lessons = {l["id"]: l for m in COURSE for l in m["lessons"]}

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=root, **k)

        def log_message(self, *a):
            pass

        def send_json(self, obj):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                body = b"<!doctype html><meta charset=utf-8><title>Curso falso</title><h1>Curso falso</h1>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                return self.wfile.write(body)
            if self.path == "/api/modules":
                return self.send_json([{"title": m["title"], "lessons": [{"id": l["id"], "title": l["title"]}
                                                                         for l in m["lessons"]]} for m in COURSE])
            if self.path.startswith("/api/lessons/"):
                l = lessons[self.path.rsplit("/", 1)[1]]
                return self.send_json({"title": l["title"], "html": l.get("html", ""), "duration": 4 if l["video"] else None,
                                       "video": f"{base}/media/{l['id']}/master.m3u8" if l["video"] else None,
                                       "files": [{"name": fn, "url": f"/files/{l['id']}/{fn}"} for fn in l["files"]]})
            return super().do_GET()

    http.server.ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    root = tempfile.mkdtemp(prefix="cbk-fake.")
    build(root)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    print(f"curso falso em http://127.0.0.1:{port} ({root})", flush=True)
    serve(root, port)
