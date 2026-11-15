"""Credential vault: private/accounts/<file>.txt, 'key: value' lines, mode 0600, gitignored. Values never go in results."""
import os, re, tempfile
from .paths import ROOT

DIR = ROOT / "private" / "accounts"

def path(name):
    if not name or not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name.startswith("."): raise ValueError("file must be a plain name like 'github.txt'")
    return DIR / (name if "." in name else name + ".txt")

def pairs(text):
    return {k.strip(): v.strip() for k, _, v in (l.partition(":") for l in text.splitlines() if ":" in l and not l.lstrip().startswith("#"))}

def read(name): p = path(name); return p.read_text() if p.exists() else ""

def set_key(name, key, value, note=None):
    p = path(name); DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    lines = [l for l in read(name).splitlines() if not l.startswith(f"{key}:")]
    if note and note not in lines: lines.insert(0, "# " + note.replace("\n", " "))
    lines.append(f"{key}: {value}")
    fd, tmp = tempfile.mkstemp(dir=DIR); os.write(fd, ("\n".join(lines) + "\n").encode()); os.close(fd)
    os.chmod(tmp, 0o600); os.replace(tmp, p)
