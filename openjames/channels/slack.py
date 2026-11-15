"""Slack bot over REST polling of its direct messages (no public URL, no Socket Mode)."""
from __future__ import annotations
import os, time
from . import Channel, Message
from ._http import call

API = "https://slack.com/api"


def _api(method, http="GET", **kw):
    r = call(http, f"{API}/{method}", headers={"Authorization": "Bearer " + os.environ["SLACK_BOT_TOKEN"]}, **kw)
    if not r.get("ok"): raise RuntimeError(r.get("error", "slack error"))
    return r


class Slack(Channel):
    name = "slack"
    env_keys = ["SLACK_BOT_TOKEN"]
    help = "api.slack.com/apps > Create App > scopes im:history, im:read, chat:write, users:read > Install > copy the xoxb- token. Your member id: profile > Copy member ID."
    id_hint = "your Slack member id (U01234...)"

    def __init__(self): self.oldest = {}; self.start = f"{time.time():.6f}"

    def check(self):
        try: _api("auth.test"); return None
        except Exception as e: return f"bot token rejected ({e})"

    def poll(self):
        out = []
        for im in _api("conversations.list", params={"types": "im", "limit": 100}).get("channels", []):
            if im.get("user") not in self.allowed: continue
            o = self.oldest.get(im["id"], self.start)
            for m in reversed(_api("conversations.history", params={"channel": im["id"], "oldest": o, "limit": 20}).get("messages", [])):
                self.oldest[im["id"]] = m["ts"]
                if m.get("user") == im["user"] and not m.get("bot_id") and m.get("text"): out.append(Message("slack", im["user"], m["text"]))
        return out

    def send(self, to, text):
        for i in range(0, len(text), 3500):
            _api("chat.postMessage", "POST", json={"channel": to, "text": text[i:i + 3500]})


CHANNEL = Slack
