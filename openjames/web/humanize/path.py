"""Cursor paths: cubic Bézier with randomised control points, a personal curvature bias,
optional overshoot + correction, and sub-pixel jitter. Never a straight line."""

from __future__ import annotations

import math

from .rng import Persona
from .timing import min_jerk

Point = tuple[float, float]


def _bezier(p0: Point, c1: Point, c2: Point, p3: Point, t: float) -> Point:
    u = 1 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p3[1])


def _segment(a: Point, b: Point, n: int, p: Persona, bend: float) -> list[Point]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / d, dx / d                       # unit normal to the chord
    r = p.rng
    off1 = d * bend * r.uniform(0.08, 0.28)
    off2 = d * bend * r.uniform(0.02, 0.2)
    c1 = (a[0] + dx * r.uniform(0.2, 0.4) + nx * off1, a[1] + dy * r.uniform(0.2, 0.4) + ny * off1)
    c2 = (a[0] + dx * r.uniform(0.6, 0.85) + nx * off2, a[1] + dy * r.uniform(0.6, 0.85) + ny * off2)
    pts = []
    for i in range(1, n + 1):
        t = min_jerk(i / n)
        x, y = _bezier(a, c1, c2, b, t)
        if i < n:                                  # jitter, but land exactly
            x += r.gauss(0, 0.35)
            y += r.gauss(0, 0.35)
        pts.append((x, y))
    return pts


def path(a: Point, b: Point, n: int, p: Persona) -> list[Point]:
    """`n` points from a (exclusive) to b (inclusive)."""
    d = math.hypot(b[0] - a[0], b[1] - a[1])
    if d < 2:
        return [b]
    n = max(3, n)
    bend = p.curvature * p.rng.uniform(0.5, 1.3) * (1 if p.rng.random() < 0.8 else -1)
    if d > 250 and p.rng.random() < p.overshoot_rate:
        ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
        k = d * p.rng.uniform(0.03, 0.08)
        over = (b[0] + ux * k + p.rng.gauss(0, 3), b[1] + uy * k + p.rng.gauss(0, 3))
        n1 = max(3, int(n * 0.82))
        return _segment(a, over, n1, p, bend) + _segment(over, b, max(3, n - n1), p, -bend * 0.5)
    return _segment(a, b, n, p, bend)


def max_deviation(a: Point, pts: list[Point]) -> float:
    """Largest distance of any point from the straight chord a→last (for tests/plots)."""
    b = pts[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy) or 1.0
    return max(abs((x - a[0]) * dy - (y - a[1]) * dx) / d for x, y in pts)
