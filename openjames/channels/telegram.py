from __future__ import annotations
import os, httpx
from . import Channel, Message

API = "https://api.telegram.org"


class Telegram(Channel):
    name = "telegram"
    env_keys = ["TELEGRAM_BOT_TOKEN"]

    def __init__(self): self.offset = 0

    def _url(self, m): return f"{API}/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{m}"

    def poll(self):
        r = httpx.get(self._url("getUpdates"), params={"offset": self.offset, "timeout": 25}, timeout=40,
                      follow_redirects=False, trust_env=False).json()
        out = []
        for u in r.get("result", []):
            self.offset = u["update_id"] + 1
            m = u.get("message") or {}
            if m.get("text"):
                out.append(Message("telegram", str(m["from"]["id"]), m["text"]))
        return out

    def send(self, to, text):
        for i in range(0, len(text), 4096):
            httpx.post(self._url("sendMessage"), json={"chat_id": to, "text": text[i:i + 4096]}, timeout=20,
                       follow_redirects=False, trust_env=False)


CHANNEL = Telegram
