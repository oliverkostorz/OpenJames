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

    def poll(self) -> list[Message]: raise NotImplementedError
    def send(self, to: str, text: str) -> None: raise NotImplementedError


def get(name: str) -> Channel:
    return importlib.import_module(f"openjames.channels.{name}").CHANNEL()
