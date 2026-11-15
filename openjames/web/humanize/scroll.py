"""Scrolling with uneven wheel ticks and inertia, and scroll-into-view before moving to
something offscreen."""

from __future__ import annotations

from . import timing
from .mouse import Mouse


def scroll_by(mouse: Mouse, dy: float) -> None:
    """Scroll roughly `dy` CSS px as a burst of wheel ticks that speed up then coast out."""
    p = mouse.p
    left, sign = abs(dy), (1 if dy > 0 else -1)
    while left > 1:
        burst = min(left, p.rng.uniform(300, 700))
        left -= burst
        n = max(2, int(burst / p.rng.uniform(70, 120)))
        weights = [1 + 0.8 * (1 - abs(2 * i / (n - 1) - 1)) for i in range(n)]   # ramp up/down
        tot = sum(weights)
        for w in weights:
            mouse.wheel(sign * burst * w / tot)
            timing.sleep(p.rng.uniform(0.014, 0.04) * p.speed)
        if left > 1:
            timing.sleep(p.lognormal(0.25, 0.4))      # glance, then keep going
    timing.sleep(p.lognormal(0.15, 0.3))


def into_view(mouse: Mouse, get_box, viewport_h: float, max_rounds: int = 12) -> list[float]:
    """Wheel-scroll until the box from `get_box()` sits in the middle band; return the box."""
    box = get_box()
    for _ in range(max_rounds):
        y, h = box[1], box[3]
        top, bottom = viewport_h * 0.12, viewport_h * 0.85
        if y >= top and y + h <= bottom or (h > bottom - top and y <= top and y + h >= bottom):
            return box
        target = viewport_h * mouse.p.rng.uniform(0.3, 0.55)
        scroll_by(mouse, (y + h / 2) - target)
        nb = get_box()
        if abs(nb[1] - box[1]) < 2:      # page didn't move (end of page / inner scroller)
            return nb
        box = nb
    return box
