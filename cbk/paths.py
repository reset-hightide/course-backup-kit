# O que muda entre Windows, macOS e Linux: pastas do usuário e nomes de arquivo permitidos.
import os, re, sys

APP = "course-backup-kit"
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
MAX_PART = 120  # o Windows limita o caminho inteiro a 260 caracteres (sem LongPathsEnabled)


def user_dir(kind):
    """Pasta do app para 'data' (logs, estado) ou 'cache' (vídeos sendo montados)."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
        return os.path.join(base, APP, "cache" if kind == "cache" else "data")
    if sys.platform == "darwin":
        return os.path.expanduser(f"~/Library/{'Caches' if kind == 'cache' else 'Application Support'}/{APP}")
    env, default = ("XDG_CACHE_HOME", "~/.cache") if kind == "cache" else ("XDG_DATA_HOME", "~/.local/share")
    return os.path.join(os.environ.get(env) or os.path.expanduser(default), APP)


def windows_name(part):
    """Nome válido no Windows (e em OneDrive/Google Drive): 'Módulo 1: Intro' -> 'Módulo 1 - Intro'."""
    part = part.replace(":", " -")
    part = re.sub(r'[<>"|?*\\\x00-\x1f]', "_", part)
    part = re.sub(r"\s+", " ", part).strip().rstrip(" .") or "_"
    if part.split(".")[0].upper() in RESERVED:
        part = "_" + part
    if len(part) > MAX_PART:
        stem, ext = os.path.splitext(part)
        part = stem[:MAX_PART - len(ext)].rstrip(" .") + ext
    return part


def use_windows_names(cfg):
    mode = cfg.get("safe_names", "auto")
    return mode == "windows" or (mode == "auto" and os.name == "nt")


def to_local(cfg, rel):
    """Caminho relativo vindo da página ('Módulo 1/1 Aula/x.pdf') -> partes válidas neste sistema.
    None se tentar sair da pasta ('..')."""
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    if not parts or any(p in (".", "..") for p in parts):
        return None
    if use_windows_names(cfg):
        parts = [windows_name(p) for p in parts]
    return parts
