"""Replay cursor paths as CDP Input.dispatchMouseEvent moves, and click like a person:
Gaussian click point inside the box, hover dwell, realistic press→release gap."""

from __future__ import annotations

import math
import time

from . import path as pathlib
from . import timing
from .rng import Persona


class Mouse:
    def __init__(self, cdp, persona: Persona, start: tuple[float, float] = (400.0, 300.0),
                 stream=None):
        # `stream` (cdp_ws.CDPStream to the same tab) lets moves go out on schedule without
        # waiting for Chrome's per-event ack; all mouse events then use it, so order is kept.
        self.cdp, self.p, self.stream = cdp, persona, stream
        self.x, self.y = start
        self.trace: list[tuple[float, float, float]] = []   # (t, x, y) of recent moves, for plots
        self._buttons = 0
        self.moves: list[tuple[tuple[float, float], list[tuple[float, float]]]] = []   # (start, path)

    def _send(self, type_: str, x: float, y: float, wait: bool = True, **kw) -> None:
        params = {"type": type_, "x": x, "y": y, **kw}
        if self.stream is not None and not self.stream.closed:
            if wait:
                self.stream.call("Input.dispatchMouseEvent", params)
            else:
                self.stream.post("Input.dispatchMouseEvent", params)
        else:
            self.cdp.send("Input.dispatchMouseEvent", params)

    def target_point(self, box: list[float]) -> tuple[float, float]:
        """Gaussian around the centre of [x, y, w, h], clipped to the inner 80 % of the box."""
        x, y, w, h = box
        cx, cy = x + w / 2, y + h / 2
        sx, sy = w / 2 * self.p.precision, h / 2 * self.p.precision
        px = self.p.gauss_clip(cx, sx, x + w * 0.1, x + w * 0.9)
        py = self.p.gauss_clip(cy, sy, y + h * 0.1, y + h * 0.9)
        return px, py

    def move_to(self, x: float, y: float, width: float = 20.0) -> None:
        d = math.hypot(x - self.x, y - self.y)
        if d < 1:
            return
        mt = timing.fitts(d, width, self.p)
        n = max(3, int(mt * self.p.hz / max(self.p.speed, 0.05)))
        pts = pathlib.path((self.x, self.y), (x, y), n, self.p)
        self.moves = self.moves[-200:] + [((self.x, self.y), pts)]
        dt = mt / len(pts)
        t0 = time.monotonic()
        if len(self.trace) > 5000:
            self.trace = self.trace[-2000:]
        for i, (px, py) in enumerate(pts):
            extra = {"button": "left", "buttons": 1} if self._buttons else {}
            self._send("mouseMoved", px, py, wait=i == len(pts) - 1, **extra)
            self.trace.append((time.monotonic(), px, py))
            # Keep to the schedule (CDP round-trips eat into the interval).
            lag = t0 + (i + 1) * dt - time.monotonic()
            if lag > 0:
                timing.sleep(lag)
        self.x, self.y = x, y

    def click(self, x: float, y: float, width: float = 20.0, count: int = 1) -> None:
        self.move_to(x, y, width)
        timing.hover(self.p)
        for c in range(1, count + 1):
            self._send("mousePressed", x, y, button="left", buttons=1, clickCount=c)
            self._buttons = 1
            timing.sleep(self.p.gauss_clip(0.085, 0.025, 0.04, 0.16) * self.p.speed)
            self._send("mouseReleased", x, y, button="left", buttons=0, clickCount=c)
            self._buttons = 0
            if c < count:
                timing.sleep(self.p.gauss_clip(0.11, 0.03, 0.06, 0.2) * self.p.speed)

    def wheel(self, dy: float, dx: float = 0.0) -> None:
        self._send("mouseWheel", self.x, self.y, deltaX=dx, deltaY=dy)
