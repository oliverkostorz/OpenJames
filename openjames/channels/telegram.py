from __future__ import annotations
import os, time, httpx, pathlib
from .. import media
from ..paths import INBOX
from . import Channel, Message
from ._http import call

API = "https://api.telegram.org"


class Telegram(Channel):
    name = "telegram"
    env_keys = ["TELEGRAM_BOT_TOKEN"]
    help = "Talk to @BotFather on Telegram, send /newbot, paste the token. Then just message your new bot once."
    id_hint = "your numeric Telegram user id (leave empty to auto-detect: you will message the bot)"

    def __init__(self): self.offset = 0

    def _url(self, m): return f"{API}/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{m}"

    def poll(self):
        r = call("GET", self._url("getUpdates"), params={"offset": self.offset, "timeout": 25}, timeout=40)
        out = []
        for u in r.get("result", []):
            self.offset = u["update_id"] + 1
            m = u.get("message") or {}
            sender = str((m.get("from") or {}).get("id", ""))
            if m.get("text"):
                out.append(Message("telegram", sender, m["text"]))
            else:
                text = self._media_text(m, sender)
                if text: out.append(Message("telegram", sender, text))
        return out

    def _media_text(self, m, sender):
        """Voice memos, audio files, round video notes and audio documents become text; other files are saved and noted.
        Only allow-listed senders are downloaded (a stranger must not make us fetch anything)."""
        if sender not in self.allowed: return None
        cap = (m.get("caption") or "").strip()
        for key, kind in (("voice", "voice memo"), ("audio", "audio file"), ("video_note", "video note"), ("document", "file"), ("video", "video")):
            obj = m.get(key)
            if not obj: continue
            name = obj.get("file_name") or f"{key}-{obj['file_unique_id']}"
            if key == "document" and not media.is_audio(name, obj.get("mime_type", "")): kind = "file"
            try: path = self._download(obj["file_id"], name, key)
            except Exception as e: return f"[{kind} received but download failed: {type(e).__name__}]"
            body = media.describe(path, kind) if key != "document" or kind != "file" else f"[file received: {path}]"
            return f"{cap}\n\n{body}" if cap else body
        return None

    def _download(self, file_id, name, key):
        info = call("GET", self._url("getFile"), params={"file_id": file_id})["result"]
        dest = INBOX / "files"; dest.mkdir(parents=True, exist_ok=True)
        ext = pathlib.Path(info["file_path"]).suffix or pathlib.Path(name).suffix
        path = dest / (f"tg-{int(time.time())}-{pathlib.Path(name).stem[:40]}{ext}".replace(" ", "_"))
        r = httpx.get(f"{API}/file/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{info['file_path']}", timeout=120, follow_redirects=False, trust_env=False)
        r.raise_for_status()
        if len(r.content) > 50_000_000: raise RuntimeError("file too large")
        path.write_bytes(r.content); return path

    def discover_sender(self, wait=120):
        """Wait for the first private message to the bot and return that user's id (no manual id lookup)."""
        end = time.time() + wait
        while time.time() < end:
            r = call("GET", self._url("getUpdates"), params={"offset": self.offset, "timeout": 10}, timeout=20)
            for u in r.get("result", []):
                self.offset = u["update_id"] + 1
                m = u.get("message") or {}
                if m.get("chat", {}).get("type") == "private" and m.get("from"):
                    return str(m["from"]["id"])
        return None

    def check(self):
        try: call("GET", self._url("getMe")); return None
        except Exception as e: return f"bot token rejected ({type(e).__name__})"

    def send(self, to, text):
        for i in range(0, len(text), 4096):
            call("POST", self._url("sendMessage"), json={"chat_id": to, "text": text[i:i + 4096]}, timeout=20)


CHANNEL = Telegram
