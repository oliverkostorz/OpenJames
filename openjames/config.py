"""User config: which channels/backends are active and the backend fallback order.

Written by the setup wizard to config.toml (gitignored). Secrets never live here, only in .env.
"""
from __future__ import annotations
import tomllib
from dataclasses import dataclass, field
from .paths import CONFIG

CHANNELS = ["telegram", "email", "whatsapp", "imessage", "sms", "signal", "discord", "slack", "matrix"]
BACKENDS = ["claude_code", "codex", "gemini", "openrouter", "anthropic_api"]


@dataclass
class Config:
    channels: list[str] = field(default_factory=list)   # active channels
    backends: list[str] = field(default_factory=list)   # active backends, in fallback priority order
    allowed_senders: dict[str, list[str]] = field(default_factory=dict)  # channel -> principal ids


def load(path=CONFIG) -> Config:
    if not path.exists():
        return Config()
    d = tomllib.loads(path.read_text())
    cfg = Config(d.get("channels", {}).get("active", []), d.get("backends", {}).get("priority", []),
                 d.get("allowed_senders", {}))
    for c in cfg.channels:
        if c not in CHANNELS: raise ValueError(f"unknown channel {c!r}")
    for b in cfg.backends:
        if b not in BACKENDS: raise ValueError(f"unknown backend {b!r}")
    return cfg


def dump(cfg: Config) -> str:
    q = lambda xs: "[" + ", ".join(f'"{x}"' for x in xs) + "]"
    out = [f"[channels]\nactive = {q(cfg.channels)}\n", f"[backends]\npriority = {q(cfg.backends)}\n", "[allowed_senders]"]
    out += [f"{k} = {q(v)}" for k, v in cfg.allowed_senders.items()]
    return "\n".join(out) + "\n"
