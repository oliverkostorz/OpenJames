"""Timing: Fitts's-law movement time, minimum-jerk velocity profile, think/hover pauses."""

from __future__ import annotations

import math
import time

from .rng import Persona


def fitts(distance: float, width: float, p: Persona) -> float:
    """Movement time in seconds: a + b·log2(D/W + 1), with per-move noise."""
    a, b = 0.12, 0.13
    w = max(width, 4.0)
    mt = a + b * math.log2(distance / w + 1.0)
    return max(0.08, mt * p.rng.uniform(0.85, 1.2)) * p.speed


def min_jerk(t: float) -> float:
    """Position fraction for time fraction t (slow start, fast middle, slow end)."""
    return 10 * t ** 3 - 15 * t ** 4 + 6 * t ** 5


def think(p: Persona, median: float = 0.6) -> None:
    """A short 'reading/deciding' pause before acting."""
    sleep(p.lognormal(median, 0.5))


def hover(p: Persona) -> None:
    """Dwell on the target before pressing."""
    sleep(p.lognormal(0.12, 0.35))


SPIN = 0.1   # seconds busy-waited at the end of each sleep


def sleep(sec: float) -> None:
    """Accurate sleep. Under launchd ProcessType=Background macOS coalesces timers, so
    time.sleep(0.011) really takes ~85 ms; sleep coarsely, then spin out the last stretch."""
    if sec <= 0:
        return
    end = time.monotonic() + min(sec, 10.0)
    if sec > SPIN:
        time.sleep(sec - SPIN)
    while time.monotonic() < end:
        time.sleep(0)
