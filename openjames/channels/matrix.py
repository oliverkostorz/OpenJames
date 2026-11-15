"""Matrix client-server API via /sync long polling. Works with any homeserver, E2E-unencrypted DM rooms only."""
from __future__ import annotations
import os, time, urllib.parse
from . import Channel, Message
from ._http import call


class Matrix(Channel):
    name = "matrix"
    env_keys = ["MATRIX_HOMESERVER", "MATRIX_ACCESS_TOKEN"]
    help = "Create a bot account, then Element > Settings > Help & About > Access Token. Homeserver e.g. https://matrix.org. Invite the bot to an unencrypted DM."
    id_hint = "your Matrix id, e.g. @you:matrix.org"

    def __init__(self): self.since = None; self.rooms: dict[str, str] = {}; self.me = None

    def _h(self): return {"Authorization": "Bearer " + os.environ["MATRIX_ACCESS_TOKEN"]}
    def _u(self, p): return os.environ["MATRIX_HOMESERVER"].rstrip("/") + "/_matrix/client/v3" + p

    def check(self):
        try: call("GET", self._u("/account/whoami"), headers=self._h()); return None
        except Exception as e: return f"access token rejected ({type(e).__name__})"

    def poll(self):
        self.me = self.me or call("GET", self._u("/account/whoami"), headers=self._h())["user_id"]
        r = call("GET", self._u("/sync"), headers=self._h(), params={"timeout": 20000, **({"since": self.since} if self.since else {})}, timeout=40)
        first, self.since = self.since is None, r["next_batch"]
        for rid in r.get("rooms", {}).get("invite", {}): call("POST", self._u(f"/rooms/{urllib.parse.quote(rid)}/join"), headers=self._h(), json={})
        out = []
        for rid, room in r.get("rooms", {}).get("join", {}).items():
            for ev in room.get("timeline", {}).get("events", []):
                if ev.get("type") != "m.room.message" or ev["sender"] == self.me: continue
                self.rooms[ev["sender"].lower()] = rid
                if not first and ev.get("content", {}).get("msgtype") == "m.text": out.append(Message("matrix", ev["sender"].lower(), ev["content"]["body"]))
        return out

    def send(self, to, text):
        rid = self.rooms.get(to.lower()) or call("POST", self._u("/createRoom"), headers=self._h(), json={"invite": [to], "is_direct": True})["room_id"]
        self.rooms[to.lower()] = rid
        call("PUT", self._u(f"/rooms/{urllib.parse.quote(rid)}/send/m.room.message/{int(time.time() * 1000)}"), headers=self._h(), json={"msgtype": "m.text", "body": text})


CHANNEL = Matrix
