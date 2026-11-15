"""Typing through CDP Input.dispatchKeyEvent: per-key delays (faster inside common bigrams,
slower after spaces/punctuation), occasional bursts and pauses, rare corrected typos, and
paste (Input.insertText) for long text such as a cover letter — people paste those too."""

from __future__ import annotations

import string

from . import timing
from .rng import Persona

# key -> (code, windowsVirtualKeyCode, text)
SPECIAL = {
    "Enter": ("Enter", 13, "\r"), "Tab": ("Tab", 9, ""), "Backspace": ("Backspace", 8, ""),
    "Escape": ("Escape", 27, ""), "Delete": ("Delete", 46, ""), "Space": ("Space", 32, " "),
    "ArrowUp": ("ArrowUp", 38, ""), "ArrowDown": ("ArrowDown", 40, ""),
    "ArrowLeft": ("ArrowLeft", 37, ""), "ArrowRight": ("ArrowRight", 39, ""),
    "Home": ("Home", 36, ""), "End": ("End", 35, ""), "PageUp": ("PageUp", 33, ""),
    "PageDown": ("PageDown", 34, ""),
}
COMMON_BIGRAMS = {"th", "he", "in", "er", "an", "re", "on", "at", "en", "nd", "ti", "es", "or",
                  "te", "of", "ed", "is", "it", "al", "ar", "st", "to", "nt", "ng", "ch", "ei", "ie"}
NEIGHBOURS = {"a": "sq", "s": "ad", "d": "sf", "e": "wr", "i": "uo", "o": "ip", "n": "bm",
              "r": "et", "t": "ry", "l": "k", "h": "gj", "u": "yi", "m": "n", "c": "xv"}
PASTE_OVER = 160   # characters


class Keyboard:
    def __init__(self, cdp, persona: Persona):
        self.cdp, self.p = cdp, persona

    def _key(self, type_: str, key: str, code: str = "", vk: int = 0, text: str = "",
             modifiers: int = 0, commands: list[str] | None = None) -> None:
        ev = {"type": type_, "key": key, "modifiers": modifiers}
        if code:
            ev["code"] = code
        if vk:
            ev["windowsVirtualKeyCode"] = vk
            ev["nativeVirtualKeyCode"] = vk
        if text:
            ev["text"] = ev["unmodifiedText"] = text
        if commands:
            ev["commands"] = commands
        self.cdp.send("Input.dispatchKeyEvent", ev)

    def press(self, key: str, modifiers: int = 0, commands: list[str] | None = None) -> None:
        """Press and release one named key (Enter, Tab, Escape, ArrowDown, …) or a character."""
        if key in SPECIAL:
            code, vk, text = SPECIAL[key]
        elif len(key) == 1:
            code, vk, text = _char_code(key), _char_vk(key), key
        else:
            raise ValueError(f"unknown key {key!r}")
        if modifiers & ~8:          # with Ctrl/Alt/Meta no text is produced
            text = ""
        self._key("keyDown" if text else "rawKeyDown", key, code, vk, text, modifiers, commands)
        timing.sleep(self.p.gauss_clip(0.07, 0.02, 0.03, 0.14) * self.p.speed)
        self._key("keyUp", key, code, vk, "", modifiers)

    def select_all_and_delete(self) -> None:
        self.press("a", modifiers=4, commands=["selectAll"])   # Meta+A (macOS)
        timing.sleep(self.p.lognormal(0.12, 0.3))
        self.press("Backspace")

    def type(self, text: str) -> None:
        if len(text) > PASTE_OVER:
            timing.think(self.p, 0.5)
            self.cdp.send("Input.insertText", {"text": text})
            return
        per_char = 60.0 / (self.p.wpm * 5)          # seconds per character
        prev = ""
        for i, ch in enumerate(text):
            low = ch.lower()
            if low in NEIGHBOURS and self.p.rng.random() < self.p.typo_rate:
                wrong = self.p.rng.choice(NEIGHBOURS[low])
                self._char(wrong)
                timing.sleep(self.p.lognormal(per_char * 2.5, 0.3))   # notice the mistake
                self.press("Backspace")
                timing.sleep(self.p.lognormal(per_char, 0.3))
            self._char(ch)
            d = per_char
            if (prev + low) in COMMON_BIGRAMS:
                d *= 0.7
            if prev in (" ", ".", ",", "@", "-") or ch.isupper() or ch in string.digits:
                d *= 1.4
            if self.p.rng.random() < 0.04:            # brief hesitation
                d += 0.35 * self.p.rng.lognormvariate(0, 0.5)   # unscaled; speed applies below
            timing.sleep(self.p.lognormal(d, 0.35))
            prev = low

    def _char(self, ch: str) -> None:
        if ch == "\n":
            self.press("Enter")
            return
        if ch == "\t":
            self.press("Tab")
            return
        code, vk = _char_code(ch), _char_vk(ch)
        mods = 8 if ch.isalpha() and ch.isupper() else 0      # Shift
        self._key("keyDown", ch, code, vk, ch, mods)
        timing.sleep(self.p.gauss_clip(0.055, 0.02, 0.02, 0.12) * self.p.speed)
        self._key("keyUp", ch, code, vk, "", mods)


def _char_code(ch: str) -> str:
    if ch.isascii() and ch.isalpha():
        return f"Key{ch.upper()}"
    if ch.isdigit():
        return f"Digit{ch}"
    if ch == " ":
        return "Space"
    return ""


def _char_vk(ch: str) -> int:
    if ch.isascii() and (ch.isalpha() or ch.isdigit()):
        return ord(ch.upper())
    if ch == " ":
        return 32
    return 0
