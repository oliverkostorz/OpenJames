"""ntfy.sh (or self-hosted ntfy): two topics, no account. Anyone who knows NTFY_TOPIC_IN can write to you,
so make both topics long random strings (the wizard/docs say so) and treat them as secrets."""
from __future__ import annotations
import json, os, time, httpx
from . import Channel, Message

SENDER = "ntfy"


class Ntfy(Channel):
    name = "ntfy"
    env_keys = ["NTFY_TOPIC_IN", "NTFY_TOPIC_OUT"]
    help = "No account: pick two long random topic names (e.g. `python -c 'import secrets;print(secrets.token_urlsafe(16))'`). Subscribe to the OUT topic in the ntfy app; publish to the IN topic to talk to the assistant. Optional NTFY_SERVER (default https://ntfy.sh) and NTFY_TOKEN."
    id_hint = "anything, e.g. ntfy (single-user channel)"

    def __init__(self): self.since = str(int(time.time()))

    def _base(self): return os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    def _h(self): return {"Authorization": "Bearer " + os.environ["NTFY_TOKEN"]} if os.environ.get("NTFY_TOKEN") else {}
    def _req(self, method, url, **kw):
        r = httpx.request(method, url, headers=self._h(), timeout=kw.pop("timeout", 30), follow_redirects=False, trust_env=False, **kw)
        r.raise_for_status(); return r

    def discover_sender(self): return SENDER
    def check(self):
        try: self._req("GET", f"{self._base()}/{os.environ['NTFY_TOPIC_IN']}/json", params={"poll": 1, "since": "latest"}); return None
        except Exception as e: return f"ntfy server/topic rejected ({type(e).__name__})"

    def poll(self):
        r = self._req("GET", f"{self._base()}/{os.environ['NTFY_TOPIC_IN']}/json", params={"poll": 1, "since": self.since})
        out = []
        for line in r.text.splitlines():
            try: ev = json.loads(line)
            except ValueError: continue
            if ev.get("id"): self.since = ev["id"]
            if ev.get("event") == "message" and ev.get("message"): out.append(Message("ntfy", SENDER, ev["message"]))
        return out

    def send(self, to, text):
        for i in range(0, len(text) or 1, 3500):     # stay under ntfy's 4096-byte message limit
            self._req("POST", f"{self._base()}/{os.environ['NTFY_TOPIC_OUT']}", content=text[i:i + 3500].encode())


CHANNEL = Ntfy
