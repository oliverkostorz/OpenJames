"""Channel contract. A channel turns outside messages into inbox/*.md tasks and sends outbox/*.md back.

Only allow-listed principals are accepted; everything else is dropped. Add a channel by creating a
module here that defines a `Channel` subclass named `CHANNEL` and listing it in config.CHANNELS.
"""
from __future__ import annotations
import importlib
from dataclasses import dataclass


@dataclass
class Message:
    channel: str
    sender: str
    text: str


class Channel:
    name = "base"
    env_keys: list[str] = []          # secrets the wizard must collect into .env
    platforms: list[str] = ["any"]    # e.g. ["darwin"]
    implemented = True
    help = ""                         # one-line "where do I get the credentials" hint shown by the wizard
    id_hint = "your id/address on this channel"
    allowed: list[str] = []           # set by bind(); channels that need to know the principal (DMs) use it

    def bind(self, allowed: list[str]) -> None: self.allowed = allowed
    def discover_sender(self) -> str | None:
        """Optional zero-typing setup: return the principal id once the user contacts us, else None."""
        return None
    def check(self) -> str | None:
        """Optional live credential check for `doctor`: return an error string or None when fine."""
        return None
    def poll(self) -> list[Message]: raise NotImplementedError
    def send(self, to: str, text: str) -> None: raise NotImplementedError


def get(name: str) -> Channel:
    return importlib.import_module(f"openjames.channels.{name}").CHANNEL()
