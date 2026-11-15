"""Twilio REST polling: one account serves SMS and WhatsApp, no public webhook or tunnel needed."""
from __future__ import annotations
import datetime as dt, os
import httpx
from .. import media
from . import Channel, Message
from ._http import call


class TwilioChannel(Channel):
    prefix = ""          # "whatsapp:" for WhatsApp
    from_key = ""        # env var holding our sender number

    def __init__(self): self.seen: set[str] = set(); self.started = dt.datetime.now(dt.timezone.utc)

    def _base(self): return f"https://api.twilio.com/2010-04-01/Accounts/{os.environ['TWILIO_ACCOUNT_SID']}"
    def _auth(self): return (os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    def _me(self): return self.prefix + os.environ[self.from_key]

    def check(self):
        try: call("GET", self._base() + ".json", auth=self._auth()); return None
        except Exception as e: return f"Twilio credentials rejected ({type(e).__name__})"

    def poll(self):
        r = call("GET", self._base() + "/Messages.json", auth=self._auth(),
                 params={"To": self._me(), "DateSent>": self.started.strftime("%Y-%m-%d"), "PageSize": 50})
        out = []
        for m in reversed(r.get("messages", [])):
            if m.get("direction") != "inbound" or m["sid"] in self.seen: continue
            self.seen.add(m["sid"])
            sent = dt.datetime.strptime(m["date_sent"], "%a, %d %b %Y %H:%M:%S %z") if m.get("date_sent") else self.started
            if sent < self.started: continue            # history from before the listener started
            sender = m["from"].removeprefix(self.prefix)
            text = m.get("body") or ""
            if int(m.get("num_media") or 0) and sender in self.allowed: text = media.join(text, self._media(m["sid"]))
            out.append(Message(self.name, sender, text))
        return out

    def _media(self, sid):
        """WhatsApp voice notes / MMS: Twilio lists them as sub-resources of the message."""
        try:
            notes = []
            for md in call("GET", f"{self._base()}/Messages/{sid}/Media.json", auth=self._auth()).get("media_list", []):
                r = httpx.get("https://api.twilio.com" + md["uri"].removesuffix(".json"), auth=self._auth(), timeout=120, follow_redirects=True, trust_env=False)
                r.raise_for_status()
                notes.append(media.ingest(r.content, "media." + md.get("content_type", "").split("/")[-1].split(";")[0], md.get("content_type", ""), self.name))
            return media.join(*notes)
        except Exception as e: return f"[attachment received but download failed: {type(e).__name__}]"

    def send(self, to, text):
        for i in range(0, len(text), 1500):
            call("POST", self._base() + "/Messages.json", auth=self._auth(),
                 data={"From": self._me(), "To": self.prefix + to, "Body": text[i:i + 1500]})
