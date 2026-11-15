"""Signal via signal-cli (https://github.com/AsamK/signal-cli): `brew install signal-cli`, then link or register a number."""
from __future__ import annotations
import json, os, shutil, subprocess
from pathlib import Path
from .. import media
from . import Channel, Message


class Signal(Channel):
    name = "signal"
    env_keys = ["SIGNAL_NUMBER"]
    help = "Install signal-cli, run `signal-cli link -n openjames` (scan the QR in Signal) or register a number; enter that number here."
    id_hint = "your own Signal number in E.164 form, e.g. +4915112345678"

    def _cli(self, *a): return subprocess.run(["signal-cli", "-a", os.environ["SIGNAL_NUMBER"], *a], capture_output=True, text=True, timeout=120)

    def check(self):
        return None if shutil.which("signal-cli") else "signal-cli not found on PATH"

    def poll(self):
        out = []
        for line in self._cli("-o", "json", "receive", "--timeout", "2").stdout.splitlines():
            try: env = json.loads(line)["envelope"]
            except (ValueError, KeyError): continue
            dm = env.get("dataMessage") or {}
            sender = env.get("sourceNumber") or env.get("source", "")
            body = media.join(dm.get("message"), self._attachments(dm, sender))
            if body: out.append(Message("signal", sender, body))
        return out

    def _attachments(self, dm, sender):
        """Voice notes and files: signal-cli stores them locally; only allow-listed senders are processed."""
        if sender not in self.allowed: return None
        base = Path(os.environ.get("SIGNAL_ATTACHMENT_DIR", "~/.local/share/signal-cli/attachments")).expanduser()
        notes = []
        for a in dm.get("attachments") or []:
            f = base / Path(str(a.get("id", ""))).name
            try: notes.append(media.ingest(f.read_bytes(), a.get("filename") or a.get("id", "file"), a.get("contentType", ""), "signal"))
            except Exception as e: notes.append(f"[attachment received but unreadable: {type(e).__name__}]")
        return media.join(*notes) or None

    def send(self, to, text): self._cli("send", "-m", text, to)


CHANNEL = Signal
