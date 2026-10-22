# Baixa vídeos: HLS (segmentos em paralelo, melhor variante + áudio, junta com ffmpeg) ou arquivo direto.
# Por que em paralelo: plataformas como Cloudflare Stream usam segmentos minúsculos, e o ffmpeg
# sozinho baixa um por vez (~0,3 MB/s). Com 12 threads chegou a ~7 MB/s.
import json, os, re, shutil, subprocess, tempfile, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from . import paths


def get(url, headers, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def playlist(url, headers):
    urls = []
    for l in get(url, headers).decode().splitlines():
        l = l.strip()
        m = re.search(r'#EXT-X-MAP:URI="([^"]+)"', l)
        if m:
            urls.append(urllib.parse.urljoin(url, m.group(1)))
        elif l and not l.startswith("#"):
            urls.append(urllib.parse.urljoin(url, l))
    return urls


def fetch_track(url, path, headers, threads):
    urls = playlist(url, headers)
    with ThreadPoolExecutor(threads) as ex, open(path, "wb") as f:
        for data in ex.map(lambda u: get(u, headers), urls):  # map mantém a ordem dos segmentos
            f.write(data)


def pick_variant(master, lines):
    best, bw = None, -1
    for i, l in enumerate(lines):
        if l.startswith("#EXT-X-STREAM-INF"):
            m = re.search(r"BANDWIDTH=(\d+)", l)
            b = int(m.group(1)) if m else 0
            if b > bw:
                bw, best = b, (l, urllib.parse.urljoin(master, lines[i + 1].strip()))
    if not best:
        return master, None  # já é uma media playlist
    grp = re.search(r'AUDIO="([^"]+)"', best[0])
    audio = next((urllib.parse.urljoin(master, re.search(r'URI="([^"]+)"', l).group(1)) for l in lines
                  if l.startswith("#EXT-X-MEDIA") and "TYPE=AUDIO" in l and 'URI="' in l
                  and (not grp or f'GROUP-ID="{grp.group(1)}"' in l)), None)
    return best[1], audio


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
                        "-show_entries", "stream=codec_type,width", "-of", "json", path],
                       capture_output=True, text=True)
    j = json.loads(r.stdout or "{}")
    fmt = j.get("format", {})
    width = next((s.get("width") for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
    return {"duration": round(float(fmt.get("duration", 0))), "size": int(fmt.get("size", 0)), "width": width,
            "audio": any(s.get("codec_type") == "audio" for s in j.get("streams", []))}


def download(url, out, kind="hls", headers=None, threads=12, tmp_root=None):
    """Baixa numa pasta de cache local e só no fim move para `out` (bom para pastas na nuvem)."""
    headers = headers or {}
    tmp_root = tmp_root or paths.user_dir("cache")
    os.makedirs(tmp_root, exist_ok=True)
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise RuntimeError(f"{tool} não encontrado no PATH (rode: cbk.py doctor)")
    tmp = tempfile.mkdtemp(dir=tmp_root, prefix="cbk-dl.")
    try:
        final = os.path.join(tmp, "out.mp4")
        if kind == "file":
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as r, open(final, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
        else:
            lines = get(url, headers).decode().splitlines()
            video, audio = pick_variant(url, lines)
            fetch_track(video, os.path.join(tmp, "v.mp4"), headers, threads)
            args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", os.path.join(tmp, "v.mp4")]
            if audio:
                fetch_track(audio, os.path.join(tmp, "a.mp4"), headers, threads)
                args += ["-i", os.path.join(tmp, "a.mp4"), "-map", "0:v", "-map", "1:a"]
            subprocess.run(args + ["-c", "copy", "-movflags", "+faststart", final], check=True)
        info = probe(final)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.move(final, out + ".part")
        os.replace(out + ".part", out)
        return info
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
