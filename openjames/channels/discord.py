"""Discord bot over REST polling of one DM with the allow-listed user (no gateway/websocket)."""
from __future__ import annotations
import os
from . import Channel, Message
from ._http import call

API = "https://discord.com/api/v10"


class Discord(Channel):
    name = "discord"
    env_keys = ["DISCORD_BOT_TOKEN"]
    help = "discord.com/developers > New Application > Bot > Reset Token. Invite it to a server you share, then DM it. Your user id: enable Developer Mode, right-click yourself > Copy User ID."
    id_hint = "your Discord user id (numeric)"

    def __init__(self): self.dm: dict[str, str] = {}; self.after: dict[str, str] = {}; self.me = None

    def _h(self): return {"Authorization": "Bot " + os.environ["DISCORD_BOT_TOKEN"]}

    def check(self):
        try: call("GET", API + "/users/@me", headers=self._h()); return None
        except Exception as e: return f"bot token rejected ({type(e).__name__})"

    def _dm(self, uid):
        if uid not in self.dm:
            self.dm[uid] = call("POST", API + "/users/@me/channels", headers=self._h(), json={"recipient_id": uid})["id"]
        return self.dm[uid]

    def poll(self):
        out = []
        for uid in self.allowed:
            ch = self._dm(uid)
            msgs = call("GET", f"{API}/channels/{ch}/messages", headers=self._h(), params={"limit": 20, **({"after": self.after[ch]} if ch in self.after else {})})
            if ch not in self.after and msgs:                 # first poll: skip history
                self.after[ch] = max(msgs, key=lambda m: int(m["id"]))["id"]; continue
            for m in sorted(msgs, key=lambda m: int(m["id"])):
                self.after[ch] = m["id"]
                if m["author"]["id"] == uid and m.get("content"): out.append(Message("discord", uid, m["content"]))
        return out

    def send(self, to, text):
        ch = self._dm(to)
        for i in range(0, len(text), 2000):
            call("POST", f"{API}/channels/{ch}/messages", headers=self._h(), json={"content": text[i:i + 2000]})


CHANNEL = Discord
