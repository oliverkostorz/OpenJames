"""Tiny JSONL audit log: state/audit.jsonl (gitignored)."""
import json, datetime as dt
from .paths import STATE

def log_event(event, **fields):
    try:
        STATE.mkdir(exist_ok=True)
        with (STATE / "audit.jsonl").open("a") as f:
            f.write(json.dumps({"ts": dt.datetime.now(dt.timezone.utc).isoformat(), "event": event, **fields}, default=str) + "\n")
    except OSError: pass
