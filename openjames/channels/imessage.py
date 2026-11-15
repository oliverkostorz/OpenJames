"""iMessage on macOS: read ~/Library/Messages/chat.db (needs Full Disk Access for the terminal/launchd job), send via Messages.app."""
from __future__ import annotations
import pathlib, sqlite3, subprocess
from . import Channel, Message

DB = pathlib.Path.home() / "Library/Messages/chat.db"
SEND = 'on run {who, body}\ntell application "Messages" to send body to buddy who of (1st account whose service type = iMessage)\nend run'


class IMessage(Channel):
    name = "imessage"
    env_keys = []
    platforms = ["darwin"]
    help = "No credentials. Grant Full Disk Access to your terminal (System Settings > Privacy & Security) and sign in to Messages."
    id_hint = "your phone number (+49...) or Apple ID email as it appears in Messages"

    def __init__(self, db=DB): self.db = db; self.last = None

    def _q(self, sql, args=()):
        con = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        try: return con.execute(sql, args).fetchall()
        finally: con.close()

    def check(self):
        try: self._q("select max(ROWID) from message"); return None
        except Exception as e: return f"cannot read chat.db ({type(e).__name__}); grant Full Disk Access"

    def poll(self):
        if self.last is None:                            # start from "now": never replay history
            self.last = self._q("select coalesce(max(ROWID),0) from message")[0][0]; return []
        rows = self._q("select m.ROWID, h.id, m.text from message m join handle h on h.ROWID = m.handle_id "
                       "where m.ROWID > ? and m.is_from_me = 0 and m.text is not null order by m.ROWID", (self.last,))
        if rows: self.last = rows[-1][0]
        return [Message("imessage", h.lower(), t) for _, h, t in rows]

    def send(self, to, text):
        subprocess.run(["osascript", "-e", SEND, to, text], check=True, timeout=30)


CHANNEL = IMessage
