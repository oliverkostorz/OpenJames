"""Timers: state/timers.json. due() is called by the listener each tick; a fired timer becomes an inbox task
addressed to the principal, so the reply is delivered on their channel."""
import json, uuid, datetime as dt
from .paths import INBOX, STATE
from .principal import principal

F = STATE / "timers.json"
now = lambda: dt.datetime.now(dt.timezone.utc)

def load(): return json.loads(F.read_text()) if F.exists() else []
def save(t): STATE.mkdir(exist_ok=True); F.write_text(json.dumps(t, indent=1))

def add(prompt, at=None, in_minutes=None, every_minutes=None, channel=None):
    when = dt.datetime.fromisoformat(at.replace("Z", "+00:00")) if at else now() + dt.timedelta(minutes=float(in_minutes))
    if when.tzinfo is None: when = when.replace(tzinfo=dt.timezone.utc)
    t = {"id": uuid.uuid4().hex[:8], "at": when.isoformat(), "prompt": prompt, "every_minutes": every_minutes, "channel": channel}
    save(load() + [t]); return t

def due():
    """Fire due timers: write inbox tasks, reschedule recurring ones. Returns number fired."""
    ts, keep, n = load(), [], 0
    for t in ts:
        if dt.datetime.fromisoformat(t["at"]) > now(): keep.append(t); continue
        ch, to = principal(t.get("channel"))
        if ch:
            INBOX.mkdir(exist_ok=True)
            (INBOX / f"timer-{t['id']}-{now():%Y%m%d-%H%M%S}.md").write_text(f"channel: {ch}\nsender: {to}\n\n[timer {t['id']}] {t['prompt']}\n"); n += 1
        if t.get("every_minutes"):
            t["at"] = (max(dt.datetime.fromisoformat(t["at"]), now()) + dt.timedelta(minutes=float(t["every_minutes"]))).isoformat(); keep.append(t)
    if len(keep) != len(ts) or n: save(keep)
    return n
