#!/usr/bin/env python3
"""Teste ponta a ponta do lado Python (servidor + download HLS + watcher + relatório), sem navegador.
Faz as mesmas chamadas HTTP que o client/core.js faria, nos dois modos de nome de arquivo
(como no site, e compatível com Windows). Uso: python tests/e2e.py"""
import json, os, subprocess, sys, tempfile, threading, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import fake_site  # noqa: E402
from cbk import paths  # noqa: E402

FAKE = 18899
CBK = [sys.executable, os.path.join(ROOT, "cbk.py")]
ENC = {"encoding": "utf-8", "errors": "replace"}
quote = urllib.parse.quote


def call(port, method, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=body, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def run(tmp, mode, port):
    cfg = {"name": f"Curso de teste {mode}", "adapter": "demo", "origin": f"http://127.0.0.1:{FAKE}",
           "dest": os.path.join(tmp, f"Curso {mode}"), "state_dir": os.path.join(tmp, f"state-{mode}"),
           "port": port, "safe_names": mode, "notify": [{"type": "stdout"}]}
    cfg_path = os.path.join(tmp, f"config-{mode}.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    srv = subprocess.Popen(CBK + ["serve", "-c", cfg_path], stdout=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                call(port, "GET", "/ping")
                break
            except Exception:
                time.sleep(0.1)
        assert b"CourseBackup.configure" in subprocess.run(CBK + ["js", "-c", cfg_path], capture_output=True).stdout
        assert b"CourseBackup.configure" in call(port, "GET", "/client.js")

        # o que o core.js faz: run_start, anexos (PUT), vídeos (POST /video), run_end
        call(port, "POST", "/event", json.dumps({"type": "run_start", "dry": False}).encode())
        for m in fake_site.COURSE:
            for n, l in enumerate(m["lessons"], 1):
                folder = f"{m['title']}/{n} {l['title'].replace('/', '-')}"
                for fn in l["files"]:
                    data = urllib.request.urlopen(f"http://127.0.0.1:{FAKE}/files/{l['id']}/" + quote(fn)).read()
                    call(port, "PUT", "/" + quote(f"{folder}/{fn}"), data)
                    assert json.loads(call(port, "GET", "/exists?p=" + quote(f"{folder}/{fn}")))["exists"]
                if l["video"]:
                    call(port, "POST", "/video", json.dumps({"url": f"http://127.0.0.1:{FAKE}/media/{l['id']}/master.m3u8",
                                                             "dest": folder + "/video.mp4", "group": m["title"]}).encode())
        for bad in ("../fora.txt", "a/../../fora.txt"):
            try:
                call(port, "PUT", "/" + quote(bad), b"x")
                raise AssertionError("aceitou caminho fora da pasta: " + bad)
            except urllib.error.HTTPError as e:
                assert e.code == 403, e.code
        call(port, "POST", "/event", json.dumps({"type": "run_end", "dry": False}).encode())

        seen, t0 = [], time.time()
        while not any(e["kind"] == "all_done" for e in seen):
            assert time.time() - t0 < 300, "watcher não terminou"
            out = subprocess.run(CBK + ["watch", "-c", cfg_path, "--once"], capture_output=True, timeout=300, **ENC)
            assert out.returncode == 0, out.stderr
            seen += [json.loads(l) for l in out.stdout.splitlines()]
        kinds = [(e["kind"], e.get("group")) for e in seen]
        print("\n".join(e["message"] for e in seen))
        assert ("group", "Módulo 1: Introdução") in kinds and ("group", "Módulo 2: Prática") in kinds, kinds
        assert not any(k == "problem" for k, _ in kinds), seen

        name = paths.windows_name if mode == "windows" else (lambda p: p)
        local = lambda rel: os.path.join(cfg["dest"], *[name(p) for p in rel.split("/")])
        for rel in ["Módulo 1: Introdução/1 Boas-vindas/video.mp4", "Módulo 1: Introdução/1 Boas-vindas/Slides.pdf",
                    "Módulo 1: Introdução/1 Boas-vindas/Planilha.xlsx", "Módulo 2: Prática/1 Exercício 1-2/video.mp4",
                    "Módulo 2: Prática/1 Exercício 1-2/Exercício.xlsx", "Módulo 2: Prática/2 Exercício 2/video.mp4",
                    "_Relatório do backup.md"]:
            assert os.path.exists(local(rel)), local(rel)
        if mode == "windows":
            assert os.path.isdir(os.path.join(cfg["dest"], "Módulo 1 - Introdução"))
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                                local("Módulo 2: Prática/2 Exercício 2/video.mp4")], capture_output=True, **ENC).stdout.split()
        assert sorted(probe) == ["audio", "video"], probe
        assert not os.path.exists(os.path.join(tmp, "fora.txt"))
        with open(local("_Relatório do backup.md"), encoding="utf-8") as f:
            print(f.read())
    finally:
        srv.terminate()
        srv.wait(10)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    assert paths.windows_name("Módulo 1: Introdução") == "Módulo 1 - Introdução"
    assert paths.windows_name("CON.txt") == "_CON.txt"
    assert paths.windows_name('a<b>"c"?.') == "a_b__c__"
    assert len(paths.windows_name("x" * 300 + ".pdf")) == paths.MAX_PART
    tmp = tempfile.mkdtemp(prefix="cbk-e2e.")
    site = os.path.join(tmp, "site")
    fake_site.build(site)
    threading.Thread(target=fake_site.serve, args=(site, FAKE), daemon=True).start()
    modes = ["windows"] if os.name == "nt" else ["none", "windows"]  # no Windows só existe o modo compatível
    for i, mode in enumerate(modes):
        print(f"== nomes: {mode}")
        run(tmp, mode, 18765 + i)
    print("OK", tmp)


if __name__ == "__main__":
    main()
