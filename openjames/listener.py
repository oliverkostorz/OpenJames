"""Long-running listener: poll active channels, write allow-listed messages to inbox/, send outbox results back,
and start the orchestrator. No model calls here."""
from __future__ import annotations
import subprocess, sys, time, datetime as dt
from dotenv import load_dotenv
from . import channels
from .config import load
from .paths import ENV, INBOX, OUTBOX, ROOT


def tick(chs, cfg):
    new = False
    for ch in chs:
        for m in ch.poll():
            if m.sender not in cfg.allowed_senders.get(ch.name, []): continue   # drop everyone else
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            (INBOX / f"{ch.name}-{stamp}.md").write_text(f"channel: {ch.name}\nsender: {m.sender}\n\n{m.text}\n"); new = True
    for f in OUTBOX.glob("*.md"):
        meta, _, body = f.read_text().partition("\n\n")
        d = dict(l.split(": ", 1) for l in meta.splitlines() if ": " in l)
        ch = next((c for c in chs if c.name == d.get("channel")), None)
        if ch: ch.send(d["sender"], body.strip()); f.rename(f.with_suffix(".sent"))
    if new: subprocess.Popen([sys.executable, "-m", "openjames.orchestrator"], cwd=ROOT)


def main():
    load_dotenv(ENV); cfg = load()
    chs = [channels.get(n) for n in cfg.channels if channels.get(n).implemented]
    while True:
        try: tick(chs, cfg)
        except Exception as e: print("listener error:", type(e).__name__, file=sys.stderr)
        time.sleep(3)

if __name__ == "__main__": main()
