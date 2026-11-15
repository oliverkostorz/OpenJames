"""Who the assistant works for: the first active channel with an allow-listed sender (or a named channel)."""
from .config import load

def principal(channel=None):
    cfg = load()
    for ch in ([channel] if channel else cfg.channels):
        if cfg.allowed_senders.get(ch): return ch, cfg.allowed_senders[ch][0]
    return None, None
