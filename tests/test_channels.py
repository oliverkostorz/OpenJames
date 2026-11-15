import sys, pathlib, sqlite3, tempfile, email as _e
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from openjames import channels, config
from openjames.channels import email as em, imessage as im, _http

# every channel loads, is real (no stubs) and documents its setup
for c in config.CHANNELS:
    ch = channels.get(c); assert ch.help or not ch.env_keys, c

# email: provider presets and DMARC gate
assert em.hosts("a@gmail.com", {}) == ("imap.gmail.com", "smtp.gmail.com")
assert em.hosts("a@corp.io", {"EMAIL_SMTP_HOST": "x"}) == ("imap.corp.io", "x")
ok = _e.message_from_string("Authentication-Results: mx; dmarc=pass\nFrom: a@b\n\nhi")
bad = _e.message_from_string("From: a@b\n\nhi")
assert em.authenticated(ok) and not em.authenticated(bad) and em.text_of(ok).strip() == "hi"

# imessage: skips history, then yields only new inbound texts
d = pathlib.Path(tempfile.mkdtemp()) / "chat.db"
con = sqlite3.connect(d)
con.executescript("create table handle(ROWID integer primary key, id text);"
                  "create table message(ROWID integer primary key, handle_id int, text text, is_from_me int);"
                  "insert into handle values(1,'+491');insert into message values(1,1,'old',0);")
con.commit()
ch = im.IMessage(d); assert ch.poll() == []
con.execute("insert into message values(2,1,'new',0)"); con.execute("insert into message values(3,1,'mine',1)"); con.commit()
assert [(m.sender, m.text) for m in ch.poll()] == [("+491", "new")] and ch.poll() == []

# fake HTTP transport for the REST channels
calls = []
def fake(responses):
    def call(method, url, **kw):
        calls.append((method, url, kw)); return responses(method, url, kw)
    return call

from openjames.channels import telegram, discord, slack, matrix, _twilio
import os; os.environ.update(TELEGRAM_BOT_TOKEN="t", DISCORD_BOT_TOKEN="d", SLACK_BOT_TOKEN="s", MATRIX_HOMESERVER="https://h",
    MATRIX_ACCESS_TOKEN="m", TWILIO_ACCOUNT_SID="AC", TWILIO_AUTH_TOKEN="x", TWILIO_FROM="+1", TWILIO_WHATSAPP_FROM="+2")

telegram.call = fake(lambda *a: {"result": [{"update_id": 5, "message": {"chat": {"type": "private"}, "from": {"id": 42}, "text": "yo"}}]})
t = telegram.Telegram(); assert t.discover_sender(5) == "42" and t.offset == 6
assert [(m.sender, m.text) for m in t.poll()] == [("42", "yo")]

discord.call = fake(lambda m, u, k: {"id": "9"} if m == "POST" else
                    ([{"id": "3", "author": {"id": "7"}, "content": "hi"}] if "after" in k["params"] else [{"id": "2", "author": {"id": "7"}, "content": "old"}]))
dc = discord.Discord(); dc.bind(["7"]); assert dc.poll() == []
discord.call = fake(lambda m, u, k: [{"id": "3", "author": {"id": "7"}, "content": "hi"}, {"id": "4", "author": {"id": "bot"}, "content": "x"}])
assert [m.text for m in dc.poll()] == ["hi"]

slack.call = fake(lambda m, u, k: {"ok": True, "channels": [{"id": "D1", "user": "U1"}, {"id": "D2", "user": "U2"}]} if "list" in u else
                  {"ok": True, "messages": [{"ts": "2", "user": "U1", "text": "b"}, {"ts": "1", "user": "U1", "text": "a"}]})
sl = slack.Slack(); sl.bind(["U1"]); assert [m.text for m in sl.poll()] == ["a", "b"]

def mx(m, u, k):
    if u.endswith("whoami"): return {"user_id": "@bot:h"}
    return {"next_batch": "n", "rooms": {"join": {"!r:h": {"timeline": {"events": [
        {"type": "m.room.message", "sender": "@Me:h", "content": {"msgtype": "m.text", "body": "hey"}}]}}}}}
matrix.call = fake(mx); mt = matrix.Matrix(); assert mt.poll() == []     # first sync = history
assert [(m.sender, m.text) for m in mt.poll()] == [("@me:h", "hey")] and mt.rooms["@me:h"] == "!r:h"

import datetime as dt
now = dt.datetime.now(dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
_twilio.call = fake(lambda m, u, k: {"messages": [{"sid": "1", "direction": "inbound", "from": "whatsapp:+49", "body": "w", "date_sent": now}]})
from openjames.channels import whatsapp
w = whatsapp.WhatsApp(); w.started -= dt.timedelta(minutes=1)
assert [(m.sender, m.text) for m in w.poll()] == [("+49", "w")] and w.poll() == []
print("ok")
