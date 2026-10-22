#!/usr/bin/env python3
"""course-backup-kit: backup organizado de cursos online que você já comprou.

  cbk.py serve  -c config.json          sobe o servidor local que grava os arquivos
  cbk.py js     -c config.json [--run]  gera o script para colar/injetar na página do curso
  cbk.py watch  -c config.json [--once] avisa a cada módulo concluído, problema ou fim
  cbk.py report -c config.json          escreve o "_Relatório do backup.md" na pasta do curso
  cbk.py video  URL SAIDA.mp4 [--file]  baixa um único vídeo (HLS ou arquivo direto)
  cbk.py doctor [-c config.json]        confere Python, ffmpeg, pastas e porta neste computador
"""
import argparse, json, os, shutil, socket, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from cbk import client, config, hls, paths, server, watch  # noqa: E402

INSTALL_FFMPEG = {"nt": "winget install Gyan.FFmpeg   (ou: choco install ffmpeg)",
                  "darwin": "brew install ffmpeg",
                  "linux": "sudo apt install ffmpeg   (Fedora: sudo dnf install ffmpeg; Arch: sudo pacman -S ffmpeg)"}


def doctor(cfg_path):
    ok = True

    def check(cond, good, bad):
        nonlocal ok
        print(("  ok   " if cond else "  FALTA ") + (good if cond else bad))
        ok = ok and cond

    print(f"Sistema: {sys.platform}, Python {sys.version.split()[0]}")
    check(sys.version_info >= (3, 10), "Python 3.10+", "Python 3.10 ou mais novo: https://www.python.org/downloads/")
    plat = "nt" if os.name == "nt" else sys.platform if sys.platform == "darwin" else "linux"
    for tool in ("ffmpeg", "ffprobe"):
        check(shutil.which(tool), f"{tool}: {shutil.which(tool)}", f"{tool} no PATH. Instale: {INSTALL_FFMPEG[plat]}")
    print(f"  dados: {paths.user_dir('data')}\n  cache: {paths.user_dir('cache')}")
    if cfg_path and os.path.exists(cfg_path):
        cfg = config.load(cfg_path)
        near = cfg["dest"]
        while not os.path.exists(near) and os.path.dirname(near) != near:
            near = os.path.dirname(near)
        check(os.access(near, os.W_OK), f"pasta do curso: {cfg['dest']}", f"sem permissão de escrita em {near}")
        with socket.socket() as s:
            free = s.connect_ex(("127.0.0.1", cfg["port"])) != 0
        print(f"  porta {cfg['port']}: " + ("livre" if free else "em uso (servidor já rodando?)"))
        print(f"  nomes de arquivo: {'compatíveis com Windows' if paths.use_windows_names(cfg) else 'como no site'}")
        print(f"  log: {cfg['log']}")
    print("Tudo certo." if ok else "Resolva o que falta e rode de novo.")
    return ok


def main():
    for stream in (sys.stdout, sys.stderr):  # console do Windows não é UTF-8 por padrão (acentos, emoji)
        stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("serve", "js", "watch", "report"):
        p = sub.add_parser(name)
        p.add_argument("-c", "--config", default="config.json")
        if name == "js":
            p.add_argument("--run", choices=["dry", "real"], help="já chama CourseBackup.run no fim do script")
        if name == "watch":
            p.add_argument("--once", action="store_true", help="imprime o primeiro aviso novo como JSON e sai")
            p.add_argument("--init", action="store_true", help="marca os módulos já concluídos como avisados")
    p = sub.add_parser("doctor")
    p.add_argument("-c", "--config")
    p = sub.add_parser("video")
    p.add_argument("url")
    p.add_argument("out")
    p.add_argument("--file", action="store_true", help="URL é um arquivo de vídeo direto, não um .m3u8")
    p.add_argument("-H", "--header", action="append", default=[], help="'Nome: valor'")
    a = ap.parse_args()

    if a.cmd == "doctor":
        sys.exit(0 if doctor(a.config) else 1)
    if a.cmd == "video":
        headers = dict(h.split(": ", 1) for h in a.header)
        print(json.dumps(hls.download(a.url, os.path.abspath(a.out), "file" if a.file else "hls", headers)))
        return
    cfg = config.load(a.config)
    if a.cmd == "serve":
        server.serve(cfg)
    elif a.cmd == "js":
        print(client.build_js(cfg, a.run))
    elif a.cmd == "watch":
        watch.watch(cfg, once=a.once, init=a.init)
    elif a.cmd == "report":
        print(watch.report(cfg))


if __name__ == "__main__":
    main()
