# Para onde vão os avisos do watcher. Cada item de "notify" no config é um destino.
#   {"type": "stdout"}
#   {"type": "desktop"}                                          notificação do sistema (Windows, macOS, Linux)
#   {"type": "command", "cmd": ["notify-send", "Backup"]}       mensagem vai como último argumento
#   {"type": "ntfy", "topic": "meu-topico-secreto", "server": "https://ntfy.sh"}
#   {"type": "webhook", "url": "https://...", "field": "text"}   POST JSON {field: mensagem}
#   {"type": "telegram", "token": "...", "chat_id": "..."}
#   {"type": "callmebot", "phone": "+55...", "apikey": "..."}    WhatsApp sem navegador (serviço de terceiros)
# Aviso pelo WhatsApp Web via Claude in Chrome não passa por aqui: o watcher roda com --once e o
# Claude Code manda a mensagem (veja .claude/skills/course-backup/SKILL.md).
import json, os, shutil, subprocess, sys, urllib.parse, urllib.request


def _post(url, data, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    urllib.request.urlopen(req, timeout=20).read()


def desktop(title, text):
    if os.name == "nt":
        # balão da bandeja via .NET, sem módulos extras; textos por variável de ambiente (sem problema de aspas)
        ps = ("Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing;"
              "$n=New-Object System.Windows.Forms.NotifyIcon; $n.Icon=[System.Drawing.SystemIcons]::Information;"
              "$n.Visible=$true; $n.ShowBalloonTip(10000,$env:CBK_TITLE,$env:CBK_TEXT,'Info'); Start-Sleep 10; $n.Dispose()")
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                         env={**os.environ, "CBK_TITLE": title, "CBK_TEXT": text})
    elif sys.platform == "darwin":
        subprocess.run(["osascript", "-e", "on run argv", "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
                        "-e", "end run", title, text], timeout=30)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", title, text], timeout=30)
    else:
        raise RuntimeError("notify-send não instalado")


def send(cfg, text):
    for n in cfg["notify"]:
        try:
            t = n["type"]
            if t == "stdout":
                print(text, flush=True)
            elif t == "desktop":
                desktop(n.get("title", cfg["name"]), text)
            elif t == "command":
                subprocess.run([*n["cmd"], text], timeout=30)
            elif t == "ntfy":
                _post(n.get("server", "https://ntfy.sh").rstrip("/") + "/" + n["topic"], text.encode())
            elif t == "webhook":
                _post(n["url"], json.dumps({n.get("field", "text"): text}).encode(), {"Content-Type": "application/json"})
            elif t == "telegram":
                _post(f"https://api.telegram.org/bot{n['token']}/sendMessage",
                      urllib.parse.urlencode({"chat_id": n["chat_id"], "text": text}).encode())
            elif t == "callmebot":
                q = urllib.parse.urlencode({"phone": n["phone"], "apikey": n["apikey"], "text": text})
                urllib.request.urlopen("https://api.callmebot.com/whatsapp.php?" + q, timeout=30).read()
            else:
                print(f"notify: tipo desconhecido {t}", file=sys.stderr)
        except Exception as e:
            print(f"notify {n.get('type')}: falhou ({e})", file=sys.stderr)
