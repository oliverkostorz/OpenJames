"""One pass = one task. Triggered by listeners/timers; drains inbox/*.md oldest first."""
from __future__ import annotations
import fcntl, os
from dotenv import load_dotenv
from . import backends, channels, guards
from .config import load
from .paths import INBOX, OUTBOX, ROOT, STATE, MEMORY, ENV


def build_system() -> str:
    parts = [(ROOT / "instructions" / n).read_text() for n in ("meta.md",) if (ROOT / "instructions" / n).exists()]
    notes = MEMORY / "README.md"
    if notes.exists(): parts.append("# Memory index\n" + notes.read_text()[:4000])
    return "\n\n".join(parts)


def handle(path) -> None:
    cfg = load()
    meta, _, body = path.read_text().partition("\n\n")
    ch, sender = None, None
    for line in meta.splitlines():
        if line.startswith("channel:"): ch = line.split(":", 1)[1].strip()
        if line.startswith("sender:"): sender = line.split(":", 1)[1].strip()
    name, reply = backends.run_chain(cfg.backends, build_system(), body)
    reply = guards.scrub(reply)
    (OUTBOX / path.name).write_text(f"channel: {ch}\nsender: {sender}\n\n{reply}\n")
    path.rename(path.with_suffix(".done"))


def main() -> int:
    load_dotenv(ENV)
    STATE.mkdir(exist_ok=True)
    lock = open(STATE / ".run.lock", "w")
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("already running"); return 0
    for task in sorted(INBOX.glob("*.md")): handle(task)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
