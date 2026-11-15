"""Long-running listener: poll active channels, write allow-listed messages to inbox/, send outbox results back,
and start the orchestrator. No model calls here."""
from __future__ import annotations
import subprocess, sys, time, datetime as dt
from dotenv import load_dotenv
from . import channels, timers
from .config import load
from .paths import ENV, INBOX, OUTBOX, ROOT


def tick(chs, cfg):
    new = timers.due() > 0
    for ch in chs:
        try: msgs = ch.poll()
        except Exception as e:                       # one broken channel must not silence the others
            print(f"{ch.name} poll error:", type(e).__name__, file=sys.stderr); continue
        for m in msgs:
            if m.sender not in cfg.allowed_senders.get(ch.name, []): continue   # drop everyone else
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            (INBOX / f"{ch.name}-{stamp}.md").write_text(f"channel: {ch.name}\nsender: {m.sender}\n\n{m.text}\n"); new = True
    for f in OUTBOX.glob("*.md"):
        meta, _, body = f.read_text().partition("\n\n")
        d = dict(l.split(": ", 1) for l in meta.splitlines() if ": " in l)
        ch = next((c for c in chs if c.name == d.get("channel")), None)
        if not ch: continue
        try: ch.send(d["sender"], body.strip()); f.rename(f.with_suffix(".sent"))
        except Exception as e: print(f"{ch.name} send error:", type(e).__name__, file=sys.stderr)
    if new: subprocess.Popen([sys.executable, "-m", "openjames.orchestrator"], cwd=ROOT)


def main():
    load_dotenv(ENV); cfg = load()
    chs = [channels.get(n) for n in cfg.channels]
    for c in chs: c.bind(cfg.allowed_senders.get(c.name, []))
    while True:
        tick(chs, cfg)
        time.sleep(3)

if __name__ == "__main__": main()
