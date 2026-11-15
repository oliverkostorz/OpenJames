from __future__ import annotations
import os, time
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
            if m.get("text"):
                out.append(Message("telegram", str(m["from"]["id"]), m["text"]))
        return out

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
